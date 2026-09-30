# -*- coding: utf-8 -*-
"""把网站相关文件部署到服务器（部署期工具，日常更新也可以用它）。

用法::

    SNUT_SSH_HOST='服务器地址' SNUT_SSH_PASS='服务器密码' python scripts/deploy_web.py

做的事：
1. 上传网站相关文件（snut/ 的几个模块、web/、deploy/）
2. 装 Python 依赖（fastapi / uvicorn）
3. 装并启动 systemd 服务 course-web

**不动 crontab。** 每天 6:37 那个抓取任务保持原样——它现在会顺手写快照。
"""

import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

import paramiko

HOST = os.environ.get("SNUT_SSH_HOST")
USER = "root"
REMOTE = os.environ.get("SNUT_REMOTE_DIR", "/opt/course-notifier")

# 要上传的文件（本地路径 = 远程路径，都相对项目根目录）。
#
# ⚠️ 远程路径一律用 / 分隔。用 Windows 的 \ 会让文件以
#    "snut\config.py" 这种名字落在项目根目录，而不是进 snut/ 子目录——
#    而且不会报错，只会静默错位。
FILES = [
    "snut/config.py",
    "snut/main.py",
    "snut/snapshot.py",
    "snut/webapp.py",
    "web/index.html",
    "web/app.js",
    "web/style.css",
    "deploy/course-web.service",
    "DEPLOY-WEB.md",
]


def connect(password):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    for attempt in range(1, 5):
        try:
            client.connect(
                HOST, username=USER, password=password,
                timeout=45, banner_timeout=45, auth_timeout=45,
            )
            return client
        except Exception as exc:
            print("[..] 连接重试 %d/4：%s" % (attempt, type(exc).__name__))
            if attempt == 4:
                raise
            time.sleep(5)


def run(client, command, label=None, check=True):
    """在远程执行命令，返回 (输出, 退出码)。"""
    if label:
        print("\n>>> %s" % label)
    _, out, err = client.exec_command(command, timeout=900)
    stdout = out.read().decode("utf-8", "replace").strip()
    stderr = err.read().decode("utf-8", "replace").strip()
    code = out.channel.recv_exit_status()
    if stdout:
        print(stdout)
    if stderr and (code != 0 or "WARNING" not in stderr):
        print("[stderr] %s" % stderr)
    if check and code != 0:
        raise SystemExit("命令失败（退出码 %d）：%s" % (code, command))
    return stdout, code


def main():
    password = os.environ.get("SNUT_SSH_PASS")
    if not password:
        print("[X] 请设置环境变量 SNUT_SSH_PASS")
        return 1
    if not HOST:
        print("[X] 请设置环境变量 SNUT_SSH_HOST")
        return 1

    local_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    missing = [f for f in FILES if not os.path.exists(os.path.join(local_root, f))]
    if missing:
        print("[X] 本地缺少文件：%s" % missing)
        return 1

    client = connect(password)
    try:
        sftp = client.open_sftp()

        # 先把远程目录建出来，否则 put 会失败
        dirs = sorted({os.path.dirname(f).replace("\\", "/") for f in FILES})
        for d in dirs:
            if not d:
                continue
            with_dirs = "%s/%s" % (REMOTE, d)
            run(client, "mkdir -p '%s'" % with_dirs, check=False)

        print("\n>>> 上传 %d 个文件" % len(FILES))
        for rel in FILES:
            remote_path = "%s/%s" % (REMOTE, rel.replace("\\", "/"))
            sftp.put(os.path.join(local_root, rel), remote_path)
            print("    %s" % rel)

        sftp.close()

        # 清掉旧字节码，避免 .pyc 与新源码版本不一致
        run(client, "find %s/snut -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null; true"
            % REMOTE, check=False)

        run(client,
            "cd %s && .venv/bin/pip install -q fastapi uvicorn 2>&1 | tail -5; "
            ".venv/bin/python -c 'import fastapi, uvicorn; "
            "print(\"fastapi\", fastapi.__version__, \"| uvicorn\", uvicorn.__version__)'"
            % REMOTE,
            label="安装 Python 依赖")

        run(client,
            "cd %s && .venv/bin/python -m snut.main --dry-run 2>&1 | tail -12"
            % REMOTE,
            label="跑一次抓取，生成网站数据快照（不发邮件）")

        run(client,
            "cp %s/deploy/course-web.service /etc/systemd/system/ && "
            "systemctl daemon-reload && systemctl enable --now course-web"
            % REMOTE,
            label="安装并启动 systemd 服务")

        time.sleep(4)

        run(client, "systemctl is-active course-web", label="服务状态（应为 active）")
        run(client, "curl -s --max-time 10 http://127.0.0.1:8000/healthz",
            label="健康检查")

        print("\n>>> 数据目录权限")
        run(client, "ls -la %s/data/ 2>/dev/null || echo '(还没有 data 目录)'" % REMOTE,
            check=False)

        print("\n完成。")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
