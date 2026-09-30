# -*- coding: utf-8 -*-
"""在远程服务器上执行命令（部署期临时工具）。

用法::

    SNUT_SSH_HOST='服务器地址' SNUT_SSH_PASS='密码' python scripts/remote.py "<命令>"
"""

import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

import paramiko

HOST = os.environ.get("SNUT_SSH_HOST")
USER = "root"
REMOTE = os.environ.get("SNUT_REMOTE_DIR", "/opt/course-notifier")


def main():
    if len(sys.argv) < 2:
        print("用法: python _run.py \"<命令>\"")
        return 1

    password = os.environ.get("SNUT_SSH_PASS")
    if not password:
        print("[X] 请设置 SNUT_SSH_PASS")
        return 1
    if not HOST:
        print("[X] 请设置 SNUT_SSH_HOST")
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    for attempt in range(1, 5):
        try:
            client.connect(
                HOST, username=USER, password=password,
                timeout=45, banner_timeout=45, auth_timeout=45,
            )
            break
        except Exception as exc:
            print("[..] 重试 %d：%s" % (attempt, type(exc).__name__))
            if attempt == 4:
                print("[X] 无法连接")
                return 1
            time.sleep(5)

    cmd = sys.argv[1]
    if cmd.startswith("!"):
        # 以 ! 开头表示在项目目录下执行
        cmd = "cd %s && %s" % (REMOTE, cmd[1:])

    _, out, err = client.exec_command(cmd, timeout=600)
    o = out.read().decode("utf-8", "replace")
    e = err.read().decode("utf-8", "replace")

    if o.strip():
        print(o.strip())
    if e.strip():
        print("[stderr]")
        print(e.strip()[:2000])

    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
