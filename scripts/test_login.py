# -*- coding: utf-8 -*-
"""登录测试脚本 —— 项目第一步。

用法::

    python scripts/test_login.py

它做什么
--------
1. 从 .env 读取学号和密码
2. 尝试登录学校统一身份认证
3. 明确报告结果：成功 / 密码错误 / 需要验证码
4. 登录成功后访问课表页，验证会话确实可用

调试产物（登录页 HTML、课表页 HTML）会存到 ``logs/`` 目录。
"""

import logging
import sys
import traceback
from pathlib import Path

# 让脚本能 import 到项目根目录下的 snut 包
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Windows 控制台默认用 GBK，中文会乱码，这里强制 UTF-8
if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

from snut.auth import AuthError, CaptchaRequired, LoginClient  # noqa: E402
from snut.config import ConfigError, get_config  # noqa: E402

LINE = "=" * 62


def _dump(path, content, label):
    """保存调试文件。"""
    try:
        path.write_text(content, encoding="utf-8")
        print("  · %s 已保存到 %s" % (label, path))
    except OSError as exc:
        print("  · %s 保存失败：%s" % (label, exc))


def main():
    print(LINE)
    print("  陕西理工大学课表推送 —— 登录测试")
    print(LINE)
    print()

    # ---------- 1. 读配置 ----------
    try:
        config = get_config()
    except ConfigError as exc:
        print("[X] 配置有问题：")
        print("    %s" % exc)
        print()
        print("    请检查项目根目录的 .env 文件。")
        return 1

    config.ensure_dirs()

    print("  学号        : %s" % config.username)
    print("  密码        : %s" % ("*" * len(config.password)))
    print("  认证服务器  : %s" % config.auth_base)
    print("  教务系统    : %s" % config.eams_base)
    print()

    client = LoginClient(config)

    # ---------- 2. 抓登录页（先看结构，再看验证码） ----------
    print("[1/3] 读取登录页 ...")
    try:
        params, page_html, has_captcha = client._fetch_login_page(
            config.sso_service_url
        )
    except Exception as exc:
        print("[X] 无法访问登录页：%s" % exc)
        print("    请确认网络能打开 %s" % config.auth_base)
        return 1

    _dump(config.log_dir / "debug_login_page.html", page_html, "登录页 HTML")
    print("      execution       = %s" % params["execution"])
    print("      pwdEncryptSalt  = %s" % params["pwdEncryptSalt"])
    print("      验证码图片元素  = %s" % ("找到（需要验证码）" if has_captcha else "未找到（无需验证码）"))
    print()

    # ---------- 3. 提交登录 ----------
    print("[2/3] 提交登录 ...")
    try:
        session = client.login()
    except CaptchaRequired as exc:
        print()
        print("[!] 需要图形验证码")
        print("    %s" % exc)
        print()
        print("    —— 下一步：接入 ddddocr 自动识别验证码，或改用持久会话方案。")
        return 2
    except AuthError as exc:
        print()
        print("[X] 登录失败")
        print("    %s" % exc)
        return 1
    except Exception as exc:
        print()
        print("[X] 未预期的错误：%s" % exc)
        traceback.print_exc()
        return 1

    print("      登录成功，已获得 EAMS 会话")
    print()

    # ---------- 4. 验证会话真的能用 ----------
    print("[3/3] 用该会话访问课表页 ...")
    url = "%s/courseTableForStd.action" % config.eams_base
    try:
        resp = session.get(url, timeout=config.http_timeout)
        resp.encoding = resp.apparent_encoding or "utf-8"
    except Exception as exc:
        print("[X] 访问课表页失败：%s" % exc)
        return 1

    if "authserver" in resp.url or "login" in resp.url.lower():
        print("[X] 被弹回登录页 —— 会话无效")
        return 1

    _dump(config.log_dir / "debug_course_page.html", resp.text, "课表页 HTML")

    n_chars = len(resp.text)
    print("      HTTP %s，页面 %d 字符" % (resp.status_code, n_chars))

    if "courseTable" in resp.text or "TaskActivity" in resp.text:
        print("      页面中含有课表相关标识 —— 会话有效")
    else:
        print("      [注意] 页面里没找到课表标识，内容可能需要进一步分析")

    print()
    print(LINE)
    print("  [√] 全部通过 —— 登录环节打通，可以进入课表解析了")
    print(LINE)
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    sys.exit(main())
