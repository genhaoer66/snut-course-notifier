import datetime
import unittest

from snut.formatter import current_week_from_start
from snut.course import Activity, CourseTable
from snut import formatter


class FormatterTests(unittest.TestCase):
    def test_current_week_uses_monday_as_week_one(self):
        start = datetime.date(2026, 8, 31)
        self.assertEqual(current_week_from_start(start, start), 1)
        self.assertEqual(current_week_from_start(start, start + datetime.timedelta(days=6)), 1)
        self.assertEqual(current_week_from_start(start, start + datetime.timedelta(days=7)), 2)

    def test_dates_before_start_are_week_one(self):
        start = datetime.date(2026, 8, 31)
        self.assertEqual(current_week_from_start(start, start - datetime.timedelta(days=1)), 1)


def make_table():
    table = CourseTable()
    table.add(Activity('Course<&"', 'PRIVATE', 'Teacher<&"', 'Room<&"', [2, 3], 0, [0, 1]))
    table.add(Activity('Tuesday', 'PRIVATE', '', '', [2], 1, [2]))
    table.add(Activity('Other week', 'PRIVATE', '', '', [5], 0, [4]))
    return table

FULL_DAY_TEXT = """\
Title<& | 9月7日 星期一 · 第2周
----------------------------------
共 1 门课

第 1-2 节  Course<&"
    教室：Room<&"
    教师：Teacher<&"
    周次：2-3"""

FULL_DAY_HTML = """\
<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:16px;background:#f5f6f8;
             font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;">
  <div style="max-width:520px;margin:0 auto;">
    <div style="background:linear-gradient(135deg,#4a7cff,#6f5cff);color:#fff;
                padding:18px 20px;border-radius:12px 12px 0 0;">
      <div style="font-size:19px;font-weight:600;">Title&lt;&amp;</div>
      <div style="font-size:13px;opacity:.9;margin-top:4px;">9月7日 星期一 · 第2周</div>
    </div>
    <div style="background:#fff;padding:6px 20px 18px;border-radius:0 0 12px 12px;
                box-shadow:0 2px 8px rgba(0,0,0,.06);">
      <div style="color:#8a9099;font-size:13px;padding:12px 0 2px;">共 1 门课</div><div style="display:flex;padding:13px 0;border-bottom:1px solid #f0f1f3;">
  <div style="flex:0 0 68px;color:#4a7cff;font-weight:600;font-size:14px;
              padding-top:2px;">第1-2节</div>
  <div style="flex:1;">
    <div style="font-size:15px;color:#222;font-weight:500;line-height:1.45;">Course&lt;&amp;&quot;</div>
    <div style="color:#5f6368;font-size:13px;margin-top:4px;">📍 Room&lt;&amp;&quot;</div>
    <div style="color:#8a9099;font-size:12px;margin-top:5px;">👤 Teacher&lt;&amp;&quot; &nbsp;·&nbsp; 📅 2-3 周</div>
  </div>
</div>

    </div>
    <div style="text-align:center;color:#9aa0a6;font-size:12px;margin-top:14px;">
      由课表小助手自动发送
    </div>
  </div>
</body></html>
"""

FULL_WEEK_TEXT = """\
Title<& | 第2周
----------------------------------

【星期一】
  第1-2  节  Course<&"  Room<&"

【星期二】
  第3    节  Tuesday  待定"""

FULL_WEEK_HTML = """\
<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:16px;background:#f5f6f8;
             font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;">
  <div style="max-width:520px;margin:0 auto;">
    <div style="background:linear-gradient(135deg,#4a7cff,#6f5cff);color:#fff;
                padding:18px 20px;border-radius:12px 12px 0 0;">
      <div style="font-size:19px;font-weight:600;">Title&lt;&amp;</div>
      <div style="font-size:13px;opacity:.9;margin-top:4px;">第2周</div>
    </div>
    <div style="background:#fff;padding:6px 20px 18px;border-radius:0 0 12px 12px;
                box-shadow:0 2px 8px rgba(0,0,0,.06);">
      <div style="margin-top:16px;font-size:14px;font-weight:600;color:#4a7cff;">星期一</div><div style="display:flex;padding:13px 0;border-bottom:1px solid #f0f1f3;">
  <div style="flex:0 0 68px;color:#4a7cff;font-weight:600;font-size:14px;
              padding-top:2px;">第1-2节</div>
  <div style="flex:1;">
    <div style="font-size:15px;color:#222;font-weight:500;line-height:1.45;">Course&lt;&amp;&quot;</div>
    <div style="color:#5f6368;font-size:13px;margin-top:4px;">📍 Room&lt;&amp;&quot;</div>
    <div style="color:#8a9099;font-size:12px;margin-top:5px;">👤 Teacher&lt;&amp;&quot; &nbsp;·&nbsp; 📅 2-3 周</div>
  </div>
</div>
<div style="margin-top:16px;font-size:14px;font-weight:600;color:#4a7cff;">星期二</div><div style="display:flex;padding:13px 0;border-bottom:1px solid #f0f1f3;">
  <div style="flex:0 0 68px;color:#4a7cff;font-weight:600;font-size:14px;
              padding-top:2px;">第3节</div>
  <div style="flex:1;">
    <div style="font-size:15px;color:#222;font-weight:500;line-height:1.45;">Tuesday</div>
    <div style="color:#5f6368;font-size:13px;margin-top:4px;">📍 待定</div>
    <div style="color:#8a9099;font-size:12px;margin-top:5px;">📅 2 周</div>
  </div>
</div>

    </div>
    <div style="text-align:center;color:#9aa0a6;font-size:12px;margin-top:14px;">
      由课表小助手自动发送
    </div>
  </div>
</body></html>
"""

EMPTY_DAY_TEXT = """\
Title<& | 9月7日 星期一 · 第9周
----------------------------------

今天没有课，好好休息 ~"""

EMPTY_DAY_HTML = """\
<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:16px;background:#f5f6f8;
             font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;">
  <div style="max-width:520px;margin:0 auto;">
    <div style="background:linear-gradient(135deg,#4a7cff,#6f5cff);color:#fff;
                padding:18px 20px;border-radius:12px 12px 0 0;">
      <div style="font-size:19px;font-weight:600;">Title&lt;&amp;</div>
      <div style="font-size:13px;opacity:.9;margin-top:4px;">9月7日 星期一 · 第9周</div>
    </div>
    <div style="background:#fff;padding:6px 20px 18px;border-radius:0 0 12px 12px;
                box-shadow:0 2px 8px rgba(0,0,0,.06);">
      <div style="padding:26px 0;text-align:center;color:#8a9099;font-size:15px;">
  ☕ 今天没有课，好好休息
</div>

    </div>
    <div style="text-align:center;color:#9aa0a6;font-size:12px;margin-top:14px;">
      由课表小助手自动发送
    </div>
  </div>
</body></html>
"""

EMPTY_WEEK_TEXT = """\
Title<& | 第9周
----------------------------------

本周没有课。"""

EMPTY_WEEK_HTML = """\
<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:16px;background:#f5f6f8;
             font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;">
  <div style="max-width:520px;margin:0 auto;">
    <div style="background:linear-gradient(135deg,#4a7cff,#6f5cff);color:#fff;
                padding:18px 20px;border-radius:12px 12px 0 0;">
      <div style="font-size:19px;font-weight:600;">Title&lt;&amp;</div>
      <div style="font-size:13px;opacity:.9;margin-top:4px;">第9周</div>
    </div>
    <div style="background:#fff;padding:6px 20px 18px;border-radius:0 0 12px 12px;
                box-shadow:0 2px 8px rgba(0,0,0,.06);">
      <div style="padding:26px 0;text-align:center;color:#8a9099;font-size:15px;">
  ☕ 今天没有课，好好休息
</div>

    </div>
    <div style="text-align:center;color:#9aa0a6;font-size:12px;margin-top:14px;">
      由课表小助手自动发送
    </div>
  </div>
</body></html>
"""


class FormatterOutputTests(unittest.TestCase):
    def test_day_and_week_match_frozen_outputs(self):
        table = make_table()
        target = datetime.date(2026, 9, 7)
        for prefix, week in [('FULL', 2), ('EMPTY', 9)]:
            with self.subTest(prefix=prefix):
                self.assertEqual(formatter.format_day_text(table, target, week, 'Title<&'),
                                 globals()[prefix + '_DAY_TEXT'])
                self.assertEqual(formatter.format_day_html(table, target, week, 'Title<&'),
                                 globals()[prefix + '_DAY_HTML'])
                self.assertEqual(formatter.format_week_text(table, week, 'Title<&'),
                                 globals()[prefix + '_WEEK_TEXT'])
                self.assertEqual(formatter.format_week_html(table, week, 'Title<&'),
                                 globals()[prefix + '_WEEK_HTML'])

    def test_html_escapes_fields_and_filters_week(self):
        table = make_table()
        for output in (formatter.format_day_html(table, datetime.date(2026, 9, 7), 2, 'Title<&'),
                       formatter.format_week_html(table, 2, 'Title<&')):
            for escaped in ('Title&lt;&amp;', 'Course&lt;&amp;&quot;',
                            'Room&lt;&amp;&quot;', 'Teacher&lt;&amp;&quot;'):
                self.assertIn(escaped, output)
            for raw in ('Title<&', 'Course<&', 'Room<&', 'Teacher<&', 'Other week'):
                self.assertNotIn(raw, output)

    def test_no_week_filter(self):
        output = formatter.format_day_text(make_table(), datetime.date(2026, 9, 7))
        self.assertIn('Course<&"', output)
        self.assertIn('Other week', output)
