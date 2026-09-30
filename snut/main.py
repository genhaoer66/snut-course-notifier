# -*- coding: utf-8 -*-
"""主流程：登录 → 取课表 → 格式化 → 推送。

用法::

    python -m snut.main                  # 推送今天的课表
    python -m snut.main --for tomorrow   # 推送明天的课表
    python -m snut.main --dry-run        # 只打印，不推送（调试用）
    python -m snut.main --week 9         # 手动指定教学周次
    python -m snut.main -v               # 输出调试日志
"""

import argparse
import datetime
import json
import logging
import sys

from .auth import AuthError, CaptchaRequired, LoginClient
from .captcha import CaptchaSolver
from .config import ConfigError, get_config
from .course import CourseError, load_course_table
from .formatter import current_week_from_start, format_day_html, format_day_text
from .notify import NotifyError, push, send_alert
from .snapshot import save_snapshot

WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]


def setup_logging(config, verbose=False):
    """配置日志：同时输出到控制台和 logs/course.log。"""
    config.ensure_dirs()
    handlers = [logging.StreamHandler(sys.stdout)]
    try:
        handlers.append(
            logging.FileHandler(
                str(config.log_dir / "course.log"), encoding="utf-8"
            )
        )
    except OSError:
        pass

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def resolve_week(config, target, override=None):
    """确定目标日期属于第几教学周。

    未配置 ``SEMESTER_START`` 时返回 ``None``，表示不按周次过滤。
    """
    if override:
        return override
    if config.semester_start:
        return current_week_from_start(config.semester_start, target)
    return None


def build_parser():
    parser = argparse.ArgumentParser(
        prog="python -m snut.main", description="陕西理工大学课表自动推送"
    )
    parser.add_argument(
        "--for",
        dest="target",
        choices=["today", "tomorrow"],
        default="today",
        help="推送哪一天的课表，默认今天",
    )
    parser.add_argument("--week", type=int, default=None, help="手动指定教学周次")
    parser.add_argument(
        "--dry-run", action="store_true", help="只打印不推送，用于调试"
    )
    parser.add_argument(
        "--no-snapshot",
        action="store_true",
        help="不更新网站的课表快照（data/timetable.json）",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="输出调试日志"
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    try:
        config = get_config()
    except ConfigError as exc:
        print("[X] 配置有问题：%s" % exc, file=sys.stderr)
        return 1

    setup_logging(config, args.verbose)
    logger = logging.getLogger("snut.main")

    today = datetime.date.today()
    target = today + datetime.timedelta(days=1 if args.target == "tomorrow" else 0)
    week = resolve_week(config, target, args.week)

    logger.info(
        "开始执行：目标日期 %s（星期%s），教学周次 %s",
        target, WEEKDAY_CN[target.weekday()], week if week else "未指定",
    )

    # ---------- 1. 登录 ----------
    client = LoginClient(config)
    solver = CaptchaSolver()
    try:
        client.ensure_login(solver=solver)
    except CaptchaRequired as exc:
        logger.error("需要图形验证码，且自动识别未能通过：%s", exc)
        if not args.dry_run:
            send_alert(
                config,
                "自动登录被图形验证码拦住了，需要人工登录一次。",
                str(exc),
            )
        return 2
    except AuthError as exc:
        logger.error("登录失败：%s", exc)
        if not args.dry_run:
            send_alert(
                config,
                "自动登录失败，请检查 .env 中的学号密码是否仍然有效。",
                str(exc),
            )
        return 1

    # ---------- 2. 取课表 ----------
    try:
        table = load_course_table(client)
    except CourseError as exc:
        logger.error("获取课表失败：%s", exc)
        if not args.dry_run:
            send_alert(config, "获取课表失败。", str(exc))
        return 1

    # ---------- 3. 落地快照（供网站读取） ----------
    # 一次抓取、两个产物：邮件推给一个人，快照给全班的网站看。
    #
    # 之所以放在推送之前：邮件发失败（比如 QQ 邮箱抽风）也要留下快照，
    # 网站不该因为发信失败就停在昨天的数据上。
    # 之所以不等 dry-run 判断：本地调试网站时可以在不发信的情况下更新数据。
    if not args.no_snapshot:
        try:
            save_snapshot(table, config)
        except Exception as exc:
            # 这里故意捕获所有异常：邮件推送是主功能，快照是附带的。
            # 无论快照因为什么原因失败（磁盘满、JSON 里有不可序列化的值、
            # 权限问题……），都不该让当天的邮件发不出去。
            logger.error("保存课表快照失败（不影响邮件推送）：%s", exc)

    # ---------- 4. 格式化 ----------
    title_prefix = "今日课表" if args.target == "today" else "明日课表"
    text_body = format_day_text(table, target, week, title_prefix)
    html_body = format_day_html(table, target, week, title_prefix)
    subject = "%s %d月%d日 星期%s" % (
        title_prefix, target.month, target.day, WEEKDAY_CN[target.weekday()]
    )
    if week:
        subject += " (第%d周)" % week

    print()
    print(text_body)
    print()

    courses = table.on_day(target.weekday(), week=week)
    logger.info("共 %d 门课", len(courses))

    # ---------- 5. 推送 ----------
    if args.dry_run:
        logger.info("--dry-run 模式，跳过推送")
        if not config.mail_enabled:
            logger.warning(
                "提示：邮件尚未配置（.env 中的 SMTP_USER / SMTP_AUTH_CODE / MAIL_TO）"
            )
        return 0

    try:
        sent = push(config, subject, text_body, html_body)
    except NotifyError as exc:
        logger.error("推送失败：%s", exc)
        return 1

    logger.info("完成，已推送到：%s", "、".join(sent))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass
    sys.exit(main())
