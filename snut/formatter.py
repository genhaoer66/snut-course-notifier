# -*- coding: utf-8 -*-
"""课表格式化：把解析出的课程对象转成易读的文本 / HTML。

推送渠道不同，适合的格式也不同：

* 邮件 —— 用 :func:`format_day_html`，带样式，手机上看着舒服；
* 微信 / 纯文本 —— 用 :func:`format_day_text`。
"""

import datetime
import html as html_module

WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]


def _weekday_cn(day):
    return WEEKDAY_CN[day] if 0 <= day <= 6 else "?"


def _date_line(target, week=None):
    """标题行，如「9月21日 星期一 · 第5周」。"""
    parts = ["%d月%d日 星期%s" % (target.month, target.day, _weekday_cn(target.weekday()))]
    if week:
        parts.append("第%d周" % week)
    return " · ".join(parts)


# ----------------------------------------------------------------------
# 纯文本
# ----------------------------------------------------------------------


def format_day_text(table, target, week=None, title_prefix="今日课表"):
    """把某一天的课格式化成纯文本。

    :param table: :class:`snut.course.CourseTable`
    :param target: ``datetime.date``，要展示的那一天
    :param week: 教学周次；给定后只显示该周有课的课程
    """
    courses = table.on_day(target.weekday(), week=week)

    lines = ["%s | %s" % (title_prefix, _date_line(target, week))]
    lines.append("-" * 34)

    if not courses:
        lines.append("")
        lines.append("今天没有课，好好休息 ~")
        return "\n".join(lines)

    lines.append("共 %d 门课" % len(courses))
    for a in courses:
        lines.append("")
        lines.append("第 %s 节  %s" % (a.unit_text, a.name))
        lines.append("    教室：%s" % a.room_text)
        if a.teachers:
            lines.append("    教师：%s" % a.teachers)
        if a.week_text:
            lines.append("    周次：%s" % a.week_text)

    return "\n".join(lines)


def format_week_text(table, week, title_prefix="本周课表"):
    """把一整个教学周格式化成纯文本。"""
    today = datetime.date.today()
    # 找到该周周一的日期（仅用于标题展示，按当前日期粗略推算）
    monday = today - datetime.timedelta(days=today.weekday())

    lines = ["%s | 第%d周" % (title_prefix, week)]
    lines.append("-" * 34)

    any_course = False
    for day in range(7):
        courses = table.on_day(day, week=week)
        if not courses:
            continue
        any_course = True
        lines.append("")
        lines.append("【星期%s】" % _weekday_cn(day))
        for a in courses:
            lines.append(
                "  第%-5s节  %s  %s"
                % (a.unit_text, a.name, a.room_text)
            )

    if not any_course:
        lines.append("")
        lines.append("本周没有课。")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# HTML（邮件正文）
# ----------------------------------------------------------------------

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:16px;background:#f5f6f8;
             font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;">
  <div style="max-width:520px;margin:0 auto;">
    <div style="background:linear-gradient(135deg,#4a7cff,#6f5cff);color:#fff;
                padding:18px 20px;border-radius:12px 12px 0 0;">
      <div style="font-size:19px;font-weight:600;">{title}</div>
      <div style="font-size:13px;opacity:.9;margin-top:4px;">{subtitle}</div>
    </div>
    <div style="background:#fff;padding:6px 20px 18px;border-radius:0 0 12px 12px;
                box-shadow:0 2px 8px rgba(0,0,0,.06);">
      {body}
    </div>
    <div style="text-align:center;color:#9aa0a6;font-size:12px;margin-top:14px;">
      由课表小助手自动发送
    </div>
  </div>
</body></html>
"""

_EMPTY_BODY = """\
<div style="padding:26px 0;text-align:center;color:#8a9099;font-size:15px;">
  ☕ 今天没有课，好好休息
</div>
"""


def _course_block(a):
    """单门课的 HTML 卡片。"""
    room = html_module.escape(a.room_text)
    name = html_module.escape(a.name)
    teacher = html_module.escape(a.teachers or "")
    week = html_module.escape(a.week_text)

    meta = []
    if teacher:
        meta.append("👤 %s" % teacher)
    if week:
        meta.append("📅 %s 周" % week)
    meta_line = (
        '<div style="color:#8a9099;font-size:12px;margin-top:5px;">%s</div>'
        % " &nbsp;·&nbsp; ".join(meta)
        if meta
        else ""
    )

    return """\
<div style="display:flex;padding:13px 0;border-bottom:1px solid #f0f1f3;">
  <div style="flex:0 0 68px;color:#4a7cff;font-weight:600;font-size:14px;
              padding-top:2px;">第%s节</div>
  <div style="flex:1;">
    <div style="font-size:15px;color:#222;font-weight:500;line-height:1.45;">%s</div>
    <div style="color:#5f6368;font-size:13px;margin-top:4px;">📍 %s</div>
    %s
  </div>
</div>
""" % (html_module.escape(a.unit_text), name, room, meta_line)


def format_day_html(table, target, week=None, title_prefix="今日课表"):
    """把某一天的课格式化成 HTML 邮件正文。"""
    courses = table.on_day(target.weekday(), week=week)

    if not courses:
        body = _EMPTY_BODY
    else:
        body = "".join(_course_block(a) for a in courses)
        body = (
            '<div style="color:#8a9099;font-size:13px;padding:12px 0 2px;">'
            "共 %d 门课</div>" % len(courses)
        ) + body

    return _HTML_TEMPLATE.format(
        title=html_module.escape(title_prefix),
        subtitle=html_module.escape(_date_line(target, week)),
        body=body,
    )


def format_week_html(table, week, title_prefix="本周课表"):
    """把一整个教学周格式化成 HTML。"""
    blocks = []
    for day in range(7):
        courses = table.on_day(day, week=week)
        if not courses:
            continue
        blocks.append(
            '<div style="margin-top:16px;font-size:14px;font-weight:600;'
            'color:#4a7cff;">星期%s</div>' % _weekday_cn(day)
        )
        blocks.extend(_course_block(a) for a in courses)

    body = "".join(blocks) if blocks else _EMPTY_BODY
    return _HTML_TEMPLATE.format(
        title=html_module.escape(title_prefix),
        subtitle="第%d周" % week,
        body=body,
    )


# ----------------------------------------------------------------------
# 周次计算
# ----------------------------------------------------------------------


def current_week_from_start(start_date, today=None):
    """按开学日期推算当前是第几周（第一周从 start_date 当天算起）。

    :param start_date: 该学期第 1 周的**周一**日期
    """
    today = today or datetime.date.today()
    delta = (today - start_date).days
    if delta < 0:
        return 1
    return delta // 7 + 1
