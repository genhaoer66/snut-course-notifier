# -*- coding: utf-8 -*-
"""课表抓取与解析。

陕西理工大学使用的**树维 EAMS** 教务系统，课表接口返回的不是 JSON，
而是一段 JavaScript 代码，形如::

    var teachers = [{id:855,name:"教师 A",lab:false}];
    var activity = new TaskActivity(
        actTeacherId.join(','), actTeacherName.join(','),
        "COURSE_CODE(SECTION)",             // 课程内部标识
        "示例课程"+periodInfo+"(SECTION)",   // 课程名
        "203",
        "6302(南区)",                        // 教室
        "00000010111111111100000...",        // 周次位图（第 i 位 = 第 i 周）
        null, null, assistantName, "", "");
    index = 1*unitCount+4;                  // 落格：星期*unitCount + 节次
    table0.activities[index][table0.activities[index].length] = activity;

关键编码规则（均已实测确认）：

* ``index = 星期 * unitCount + 节次``，**星期从 0 开始**（0=周一），
  **节次也从 0 开始**（0=第1节）。
* 周次位图是纯 0/1 字符串，**下标 i 就是第 i 周**（第 0 位是恒为 '0'
  的占位符）。注意不要误当成 i+1，那会让所有课程整体偏移一周。
"""

import datetime
import logging
import re

logger = logging.getLogger(__name__)

WEEKDAY_NAMES = ["一", "二", "三", "四", "五", "六", "日"]

# 课表数据接口
COURSE_TABLE_PATH = "courseTableForStd!courseTable.action"
COURSE_PAGE_PATH = "courseTableForStd.action"
SEMESTER_QUERY_PATH = "dataQuery.action"


class CourseError(Exception):
    """课表抓取或解析失败。"""


class Activity(object):
    """一次上课安排：某门课在星期几的第几节、哪些周上、在哪间教室。"""

    def __init__(self, name, course_code, teachers, room, weeks, day, units):
        self.name = name              # 课程名
        self.course_code = course_code
        self.teachers = teachers      # 教师名字符串
        self.room = room              # 教室，可能为空（如体育课）
        self.weeks = weeks            # 有课的周次列表，如 [5, 6, 9, 10]
        self.day = day                # 0=周一 … 6=周日
        self.units = units            # 节次列表（0-based），如 [4, 5]

    # ---------- 展示用属性 ----------

    @property
    def weekday_name(self):
        if 0 <= self.day <= 6:
            return WEEKDAY_NAMES[self.day]
        return "?"

    @property
    def unit_text(self):
        """节次文本，如 "5-6" 或 "3"。"""
        if not self.units:
            return ""
        lo, hi = min(self.units) + 1, max(self.units) + 1
        return str(lo) if lo == hi else "%d-%d" % (lo, hi)

    @property
    def week_text(self):
        """周次文本，如 "5-7,9-13"。"""
        return _compress_ranges(self.weeks)

    def on_week(self, week):
        """指定周次是否有课。"""
        return week in self.weeks

    @property
    def room_text(self):
        return self.room or "待定"

    def __repr__(self):
        return "<Activity %s 周%s 第%s节 %s>" % (
            self.name, self.weekday_name, self.unit_text, self.room_text
        )


class CourseTable(object):
    """一个学期的课表。"""

    def __init__(self, semester_id=None, unit_count=11):
        self.semester_id = semester_id
        self.unit_count = unit_count
        self.activities = []

    def add(self, activity):
        self.activities.append(activity)

    def on_day(self, day, week=None):
        """取某天的课程，按节次排序。

        :param day: 0=周一 … 6=周日
        :param week: 若给定，只返回该周有课的课程
        """
        result = [
            a for a in self.activities
            if a.day == day and (week is None or a.on_week(week))
        ]
        return sorted(result, key=lambda a: min(a.units) if a.units else 99)

    def days_with_course(self, week=None):
        """返回本周有课的星期集合。"""
        return {
            a.day for a in self.activities if week is None or a.on_week(week)
        }

    def __len__(self):
        return len(self.activities)


# ----------------------------------------------------------------------
# 解析
# ----------------------------------------------------------------------

# 带换行的 activity 定义，参数顺序见模块文档
_ACTIVITY_RE = re.compile(
    r'actTeacherName\.join\(\',\'\),\s*'
    r'"([^"]*)",\s*'                       # 组1：课程标识 "952665(22319107.A5)"
    r'"([^"]*?)"\s*\+\s*periodInfo\s*\+\s*"([^"]*)",\s*'   # 组2：课程名 组3：课程代码
    r'"([^"]*)",\s*'                       # 组4：周次参数（未使用）
    r'"([^"]*)",\s*'                       # 组5：教室
    r'"([01]+)"',                          # 组6：周次位图
    re.S,
)

_TEACHERS_RE = re.compile(r'var\s+teachers\s*=\s*\[(.*?)\]\s*;', re.S)
_TEACHER_NAME_RE = re.compile(r'name\s*:\s*"([^"]*)"')
_INDEX_RE = re.compile(r'index\s*=\s*(\d+)\s*\*\s*unitCount\s*\+\s*(\d+)\s*;')
_UNIT_COUNT_RE = re.compile(r'var\s+unitCount\s*=\s*(\d+)\s*;')


def _compress_ranges(numbers):
    """把 [5,6,7,9,10] 压缩成 "5-7,9-10"。"""
    if not numbers:
        return ""
    ordered = sorted(set(numbers))
    ranges = [[ordered[0], ordered[0]]]
    for n in ordered[1:]:
        if n == ranges[-1][1] + 1:
            ranges[-1][1] = n
        else:
            ranges.append([n, n])
    return ",".join(
        str(a) if a == b else "%d-%d" % (a, b) for a, b in ranges
    )


def parse_course_table(js):
    """解析课表接口返回的 JavaScript，返回 :class:`CourseTable`。

    解析策略：先以 ``var teachers =`` 为界把响应切成若干块，
    每块对应一次排课，块内包含教师名单、TaskActivity 定义和落格语句。
    """
    unit_match = _UNIT_COUNT_RE.search(js)
    unit_count = int(unit_match.group(1)) if unit_match else 11

    table = CourseTable(unit_count=unit_count)

    # 以 var teachers 为分隔切成块（块首即教师定义）
    blocks = re.split(r'(?=var\s+teachers\s*=)', js)

    for block in blocks:
        act_match = _ACTIVITY_RE.search(block)
        if not act_match:
            continue

        course_id, name, code, _p4, room, week_bits = act_match.groups()
        name = (name or "").strip()
        if not name:
            continue

        # 教师：从 var teachers = [{id:..,name:".."}] 中取
        teacher_names = []
        tm = _TEACHERS_RE.search(block)
        if tm:
            teacher_names = [
                n for n in _TEACHER_NAME_RE.findall(tm.group(1)) if n
            ]

        # 周次位图 → 周次列表。
        #
        # ⚠️ 下标 i 直接就是**第 i 周**，不要写成 i+1！
        # 实测依据：全部 28 条记录位图的第 0 位恒为 '0'，说明它只是占位符
        # （不存在"第 0 周"）。早先按 i+1 解析会让所有课程整体偏移一周，
        # 例如把「大学体育（五）」的 1-3 周错算成 2-4 周。
        weeks = [i for i, bit in enumerate(week_bits) if bit == "1" and i > 0]
        if not weeks:
            continue

        # 落格位置：一个 activity 可能同时落在连续的多个节次上
        cells = _INDEX_RE.findall(block)
        if not cells:
            logger.debug("课程 %s 未找到落格位置，已跳过", name)
            continue

        by_day = {}
        for day_s, unit_s in cells:
            by_day.setdefault(int(day_s), []).append(int(unit_s))

        for day, units in by_day.items():
            table.add(
                Activity(
                    name=name,
                    course_code=code.strip("()"),
                    teachers="、".join(teacher_names),
                    room=room.strip(),
                    weeks=weeks,
                    day=day,
                    units=sorted(units),
                )
            )

    _merge_activities(table)
    logger.info("解析完成：%d 条排课，每天 %d 节", len(table), unit_count)
    return table


def _merge_activities(table):
    """合并同一门课在同一时段的多次排课。

    教务系统常把一门课按周次拆成多条记录（如「形势与政策」第9-10周一条、
    第11-12周另一条）。这里把 **(课程名, 教室, 教师, 星期, 节次)** 完全
    相同的记录合并，周次取并集。
    """
    merged = {}
    order = []
    for a in table.activities:
        key = (a.name, a.room, a.teachers, a.day, tuple(a.units))
        if key in merged:
            merged[key].weeks = sorted(set(merged[key].weeks) | set(a.weeks))
        else:
            merged[key] = a
            order.append(key)

    table.activities = [merged[k] for k in order]
    return table


# ----------------------------------------------------------------------
# 抓取
# ----------------------------------------------------------------------


def _pick_semester(text):
    """从含有学期列表的文本中挑出「当前学期」的 id。

    学期列表形如::

        semesters:{y0:[{id:14,schoolYear:"2010-2011",name:"1"}, ...], ...}

    选定策略：取**学年最靠后**的学期；若当前月份落在 2–7 月，
    则倾向选该学年的第二学期（name=="2"）。
    """
    entries = re.findall(
        r'\{id:(\d+),schoolYear:"([^"]+)",name:"([^"]+)"\}', text
    )
    if not entries:
        return None

    parsed = [(int(i), y, n) for i, y, n in entries]
    latest_year = max(y for _, y, _ in parsed)

    month = datetime.date.today().month
    prefer_term = "2" if 2 <= month <= 7 else "1"

    for sid, year, term in parsed:
        if year == latest_year and term == prefer_term:
            return sid
    for sid, year, term in parsed:
        if year == latest_year:
            return sid
    return parsed[-1][0]


def fetch_semester_id(client, page_html):
    """确定当前学期的 id。

    学期列表**不在**课表主页里，需要调用 ``dataQuery.action`` 拉取
    （``dataType=semesterCalendar``）。先尝试直接从主页文本解析，
    失败再发这个请求。
    """
    semester_id = _pick_semester(page_html)
    if semester_id:
        return semester_id

    # 主页里的 tagId 形如 semesterBar20826294511Semester。
    # 注意：它是 **id** 属性而不是 name，且数字每次加载都会变，必须现场提取。
    # 早期版本误写成 name="semesterBar(\d+)"，导致始终匹配不到、学期解析失败。
    m = re.search(r'semesterBar(\d+)Semester', page_html)
    tag_id = "semesterBar%sSemester" % (m.group(1) if m else "199703121")

    url = "%s/%s" % (client.config.eams_base, SEMESTER_QUERY_PATH)
    resp = client.session.post(
        url,
        data={"tagId": tag_id, "dataType": "semesterCalendar", "empty": "true"},
        headers={"X-Requested-With": "XMLHttpRequest"},
        timeout=client.config.http_timeout,
    )
    resp.encoding = resp.apparent_encoding or "utf-8"
    logger.debug("dataQuery 返回 %d 字符", len(resp.text))
    return _pick_semester(resp.text)


def fetch_ids_candidates(page_html):
    """从课表主页 JS 中提取 ``ids`` 候选值。

    页面里会按课表类型给出不同的 ids::

        if(jQuery("#courseTableType").val()=="std"){
            bg.form.addInput(form,"ids","<student-record-id>");   // 学生课表
        }else{
            bg.form.addInput(form,"ids","<other-record-id>");
        }

    返回 ``[(kind, ids), ...]``，其中 kind 为 "std" 或 "other"。
    """
    result = []
    if re.search(r'val\(\)\s*==\s*["\']std["\']', page_html):
        pass
    ids_all = re.findall(r'addInput\(form,\s*"ids",\s*"(\d+)"\)', page_html)
    if len(ids_all) >= 1:
        result.append(("std", ids_all[0]))
    if len(ids_all) >= 2:
        result.append(("other", ids_all[1]))
    return result


def fetch_course_table(client, semester_id, ids):
    """向教务系统请求课表数据，返回原始 JavaScript 文本。

    重要：``startWeek`` 必须留空。传 ``startWeek=1`` 只会返回**第 1 周**的
    课（实测结果：从 28 门课缩水成 1 门）。另外不能传 ``project.id``，
    传了会返回 HTTP 500。
    """
    url = "%s/%s" % (client.config.eams_base, COURSE_TABLE_PATH)
    page_url = "%s/%s" % (client.config.eams_base, COURSE_PAGE_PATH)
    data = {
        "ignoreHead": "1",
        "setting.kind": "std",
        "startWeek": "",          # 必须为空：表示全部周次
        "semester.id": str(semester_id),
        "ids": str(ids),
    }
    resp = client.session.post(
        url,
        data=data,
        headers={"X-Requested-With": "XMLHttpRequest", "Referer": page_url},
        timeout=client.config.http_timeout,
    )
    resp.encoding = resp.apparent_encoding or "utf-8"
    if resp.status_code != 200:
        raise CourseError("课表接口返回 HTTP %s" % resp.status_code)
    if "没有权限" in resp.text:
        raise CourseError(
            "课表接口返回『没有权限』——ids 或 semester.id 不正确。"
            "请重新运行 scripts/debug_course.py 查看当前值。"
        )
    if "过快点击" in resp.text:
        raise CourseError(
            "被教务系统限流（请不要过快点击）。请调大 .env 中的 REQUEST_INTERVAL 后重试。"
        )
    return resp.text


def load_course_table(client, semester_id=None):
    """完整流程：进入课表页 → 解析 ids 与学期 → 拉取并解析课表。"""
    page_url = "%s/%s" % (client.config.eams_base, COURSE_PAGE_PATH)
    resp = client.session.get(page_url, timeout=client.config.http_timeout)
    resp.encoding = resp.apparent_encoding or "utf-8"
    page_html = resp.text

    if "过快点击" in page_html:
        raise CourseError("被教务系统限流，请调大 REQUEST_INTERVAL 后重试。")

    candidates = fetch_ids_candidates(page_html)
    if not candidates:
        raise CourseError(
            "课表页中未找到 ids 字段。教务系统可能已改版，请运行 "
            "scripts/debug_course.py 重新分析。"
        )
    ids = candidates[0][1]
    logger.debug("ids=%s，候选：%s", ids, candidates)

    if semester_id is None:
        semester_id = fetch_semester_id(client, page_html)
        if semester_id is None:
            raise CourseError("未能解析出当前学期 id（dataQuery 接口可能已变更）。")
    logger.info("使用学期 id=%s，学生 ids=%s", semester_id, ids)

    raw = fetch_course_table(client, semester_id, ids)
    table = parse_course_table(raw)
    table.semester_id = semester_id
    return table
