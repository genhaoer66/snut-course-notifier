# -*- coding: utf-8 -*-
"""课表页抓取调试工具。

登录教务系统并把课表相关的页面/接口响应保存到 logs/ 目录，
同时打印关键字段，用于分析课表数据结构。

用法::

    python scripts/debug_course.py
"""

import logging
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

from snut.auth import AuthError, CaptchaRequired, LoginClient  # noqa: E402
from snut.config import get_config  # noqa: E402

LINE = "=" * 62


def dump(config, name, text):
    path = config.log_dir / name
    path.write_text(text, encoding="utf-8")
    print("    -> %s (%d 字符)" % (path.name, len(text)))
    return path


def main():
    config = get_config()
    config.ensure_dirs()

    client = LoginClient(config)

    print(LINE)
    print("  登录中 ...")
    print(LINE)
    try:
        client.ensure_login()
    except CaptchaRequired as exc:
        print()
        print("[!] 需要图形验证码：%s" % exc)
        print()
        print("    请执行：")
        print("        python scripts/captcha_login.py fetch")
        print("        python scripts/captcha_login.py submit <验证码>")
        return 2
    except AuthError as exc:
        print("[X] 登录失败：%s" % exc)
        return 1

    print("  已登录\n")

    # ---------- 1. 课表主页 ----------
    print("[1/3] 抓取 courseTableForStd.action ...")
    url = "%s/courseTableForStd.action" % config.eams_base
    resp = client.session.get(url, timeout=config.http_timeout)
    resp.encoding = resp.apparent_encoding or "utf-8"
    print("    HTTP %s" % resp.status_code)
    dump(config, "debug_course_main.html", resp.text)

    # 提取隐藏字段 ids（服务端下发，缺了会导致课表为空）
    ids = re.findall(r'name="ids"\s+value="([^"]*)"', resp.text)
    if not ids:
        ids = re.findall(r'id="ids"\s+value="([^"]*)"', resp.text)
    print("    ids 字段：%r" % (ids[:3] if ids else "未找到"))

    # 页面上出现的其他隐藏字段
    hidden = re.findall(
        r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', resp.text
    )
    if hidden:
        print("    页面隐藏字段：")
        for name, value in hidden[:15]:
            print("        %-20s = %r" % (name, value[:60]))

    # ---------- 2. 学期信息 ----------
    print("\n[2/3] 抓取学期列表 dataQuery.action ...")
    dq_url = "%s/dataQuery.action" % config.eams_base
    try:
        post_param = re.search(r'name="semesterBar(\d+)"', resp.text)
        tag_id = "semesterBar%sSemester" % (post_param.group(1) if post_param else "199703121")
        print("    tagId = %s" % tag_id)
        r2 = client.session.post(
            dq_url,
            data={"tagId": tag_id, "dataType": "semesterCalendar", "empty": "true"},
            headers={"X-Requested-With": "XMLHttpRequest"},
            timeout=config.http_timeout,
        )
        r2.encoding = r2.apparent_encoding or "utf-8"
        print("    HTTP %s" % r2.status_code)
        dump(config, "debug_semester.txt", r2.text)

        sem_ids = re.findall(r"(?<=id:)\d+(?=,)", r2.text)
        print("    解析到 semester.id 候选：%s" % sem_ids[:10])
    except Exception as exc:
        print("    [X] 失败：%s" % exc)

    # ---------- 3. 页面里所有 JS/CSS 引用 ----------
    print("\n[3/3] 课表页引用的资源 ...")
    for m in re.findall(r'(?:src|href)="([^"]+\.(?:js|css))"', resp.text)[:12]:
        print("    %s" % m)

    # ---------- 汇总 ----------
    print("\n" + LINE)
    body = resp.text
    for marker in ("TaskActivity", "courseTable", "table0", "unitCount", "semester"):
        print("  页面含 %-14s : %s" % (marker, "是" if marker in body else "否"))
    print(LINE)
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    sys.exit(main())
