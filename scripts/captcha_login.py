# -*- coding: utf-8 -*-
"""验证码登录工具（人工识别版）。

学校在连续登录失败若干次后会要求图形验证码。本脚本把登录拆成两步，
方便在自动识别不可用时人工介入。

用法::

    # 第一步：抓取验证码图片（会打印图片路径）
    python scripts/captcha_login.py fetch

    # 看图后，第二步：提交
    python scripts/captcha_login.py submit FRqF

两步之间不要间隔太久（验证码有效期有限，通常几分钟）。
"""

import json
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

import requests  # noqa: E402

from snut.auth import AuthError, CaptchaRequired, LoginClient  # noqa: E402
from snut.config import get_config  # noqa: E402

STATE_FILE = ROOT / ".session" / "pending_login.json"


def save_state(client, params):
    """保存会话 Cookie 与一次性参数，供第二步使用。"""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "saved_at": time.time(),
        "params": params,
        "cookies": requests.utils.dict_from_cookiejar(client.session.cookies),
    }
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_state():
    """读取第一步保存的状态。"""
    if not STATE_FILE.exists():
        raise SystemExit("找不到 %s，请先执行 fetch 步骤。" % STATE_FILE)
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    age = time.time() - state.get("saved_at", 0)
    if age > 600:
        print("[!] 提示：状态已保存 %.0f 秒，验证码可能已过期，建议重新 fetch。" % age)
    return state


def cmd_fetch():
    """第一步：抓登录页与验证码图片。"""
    config = get_config()
    config.ensure_dirs()
    client = LoginClient(config)

    print("[1/2] 抓取登录页 ...")
    params = client.prepare()
    print("      execution      = %s" % params["execution"])
    print("      pwdEncryptSalt = %s" % params["pwdEncryptSalt"])

    print("[2/2] 抓取验证码图片 ...")
    img_path = config.log_dir / "captcha_sample.png"
    data = client.fetch_captcha(save_path=img_path)
    save_state(client, params)

    print("      已保存：%s（%d 字节）" % (img_path, len(data)))
    print()
    print("  请打开上面这个图片文件查看验证码，然后执行：")
    print("      python scripts/captcha_login.py submit <你看到的字符>")
    return 0


def cmd_submit(code):
    """第二步：用验证码提交登录。"""
    config = get_config()
    state = load_state()

    client = LoginClient(config)
    # 恢复第一步的会话 Cookie，保证验证码与会话对应
    for name, value in state["cookies"].items():
        client.session.cookies.set(name, value)
    client._login_params = state["params"]

    print("提交登录（验证码：%s）..." % code)
    try:
        client.submit(captcha=code)
    except CaptchaRequired as exc:
        print()
        print("[X] 验证码被拒绝：%s" % exc)
        print("    可能识别错了，或验证码已过期。重新执行 fetch 再试一次。")
        return 2
    except AuthError as exc:
        print()
        print("[X] 登录失败：%s" % exc)
        print("    如果不是验证码问题，请检查 .env 里的学号密码。")
        return 1

    print()
    print("[√] 登录成功！")

    # 保存会话，供后续复用 —— 这能显著减少登录次数，降低再次触发验证码的概率
    client.save_session()
    print("    会话已保存到 .session/cookies.json，后续运行会自动复用")

    # 顺手验证会话能否访问课表页
    url = "%s/courseTableForStd.action" % config.eams_base
    resp = client.session.get(url, timeout=config.http_timeout)
    resp.encoding = resp.apparent_encoding or "utf-8"
    print("    课表页 HTTP %s，%d 字符" % (resp.status_code, len(resp.text)))
    if "TaskActivity" in resp.text or "courseTable" in resp.text:
        print("    页面含课表标识 —— 会话有效")

    STATE_FILE.unlink(missing_ok=True)
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    action = sys.argv[1].lower()
    if action == "fetch":
        return cmd_fetch()
    if action == "submit":
        if len(sys.argv) < 3:
            print("用法：python scripts/captcha_login.py submit <验证码>")
            return 1
        return cmd_submit(sys.argv[2].strip())
    print("未知动作：%s（应为 fetch 或 submit）" % action)
    return 1


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    sys.exit(main())
