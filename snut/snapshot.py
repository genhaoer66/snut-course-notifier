# -*- coding: utf-8 -*-
"""课表快照：把抓到的课表**脱敏**后落成 JSON，供网站读取。

网站只读这个文件，**完全不碰学校教务系统**——同学怎么刷新都不会给学校
增加压力，学校风控也波及不到网站。

三条设计原则
------------

**① 白名单导出。** 只挑出允许公开的字段写进 JSON，绝不用 ``__dict__`` /
``vars()`` 整包抛出。整包抛出的问题在于：以后给
:class:`~snut.course.Activity` 加个字段（比如学号、内部 id），会**静默**
出现在公网上，没人会发现。白名单则相反——新字段默认不公开，要显式加进来。

**② 原子写入。** 先写 ``timetable.json.tmp`` 再 ``os.replace()``。
``os.replace`` 在同一文件系统上是原子的，保证网站任何时刻读到的都是
一个完整文件，不会读到写了一半的 JSON。

**③ 失败保留旧数据。** 写入过程中出错时不删除已有快照。网站宁可显示
昨天的课表（页脚会标出更新时间），也不要白屏。
"""

import datetime
import json
import logging
import os

logger = logging.getLogger(__name__)

SNAPSHOT_NAME = "timetable.json"
PERIODS_NAME = "periods.json"

#: 允许公开到网站的字段。**改这里之前先想清楚会不会泄漏个人信息。**
#:
#: 明确排除：
#:   * 学号（根本不在 Activity 里，但要防以后被加进来）
#:   * ``ids``（学校数据库里的学生记录内部 ID，能反查到人）
#:   * ``semester_id`` / ``course_code``（前端用不到，能不给就不给）
PUBLIC_FIELDS = ("name", "teachers", "room", "day", "units", "weeks")


def build_snapshot(table, config, now=None):
    """把 :class:`~snut.course.CourseTable` 转成可公开的 dict。

    :param table: 已解析的课表
    :param config: 配置对象（取 semester_start）
    :param now: 生成时间，便于测试注入
    """
    now = now or datetime.datetime.now()
    return {
        "updated_at": now.strftime("%Y-%m-%d %H:%M"),
        "updated_ts": int(now.timestamp()),
        "semester_start": (
            config.semester_start.isoformat() if config.semester_start else None
        ),
        "unit_count": table.unit_count,
        "periods": load_periods(config),
        "courses": [
            {field: getattr(a, field) for field in PUBLIC_FIELDS}
            for a in table.activities
        ],
    }


def save_snapshot(table, config, now=None):
    """把课表脱敏后原子写入 ``data/timetable.json``。

    :return: 写入的文件路径
    :raises OSError: 写盘失败（调用方决定是告警还是忽略）
    """
    config.ensure_dirs()
    target = config.data_dir / SNAPSHOT_NAME
    tmp = target.with_name(target.name + ".tmp")

    payload = build_snapshot(table, config, now=now)
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    try:
        # 快照里有全班的教学安排，虽然不算敏感，但也没必要让同机器上的
        # 其他用户随便读。Windows 上这个调用基本是空操作，不会报错。
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, target)

    logger.info(
        "课表快照已更新：%s（%d 门课）", target, len(payload["courses"])
    )
    return target


def load_snapshot(config):
    """读取快照。文件不存在或已损坏时返回 ``None``，由调用方决定怎么提示。"""
    path = config.data_dir / SNAPSHOT_NAME
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("课表快照不存在：%s（尚未运行过抓取？）", path)
        return None
    except (OSError, ValueError) as exc:
        logger.error("课表快照读取失败：%s", exc)
        return None


def load_periods(config):
    """读取作息时间表；未配置时返回 ``None``。

    教务系统**不提供**每节课的起止时间（已验证过接口），所以这份表需要手工
    维护一次，放在 ``data/periods.json``，格式为按节次排列的起止时间::

        [["08:00", "08:45"], ["08:50", "09:35"], ...]

    没有这份文件时，前端会优雅降级成只显示节次（"第5-6节"），
    而不是显示一个编造的时间——**宁可少显示，也不能显示错的**，
    否则同学照着错时间去了教室才是真的耽误事。
    """
    path = config.data_dir / PERIODS_NAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("作息时间表读取失败，已忽略：%s", exc)
        return None

    if not isinstance(data, list) or not data:
        logger.warning("作息时间表格式不对（应为数组），已忽略：%s", path)
        return None
    return data
