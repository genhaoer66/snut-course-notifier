# -*- coding: utf-8 -*-
"""Offline parser regressions using synthetic JavaScript and in-memory objects."""

import datetime
from pathlib import Path
import unittest
from unittest.mock import patch

from snut.course import (
    Activity, CourseTable, _compress_ranges, _pick_semester, parse_course_table,
)


FIXTURE = Path(__file__).parent / "fixtures" / "course_table_sample.js"


def make_block(name="示例课程A", room="101", teachers=("教师甲",),
               bits="0110000000000000000000", cells=((2, 4),)):
    """Build one synthetic TaskActivity block, including actual placement syntax."""
    teacher_js = ",".join(
        '{id:%d,name:"%s",lab:false}' % (i, teacher)
        for i, teacher in enumerate(teachers, 1)
    )
    block = '''
var teachers = [%s];
var activity = new TaskActivity(
    actTeacherId.join(','), actTeacherName.join(','),
    "SAMPLE(SECTION)", "%s"+periodInfo+"(SECTION)",
    "0", "%s", "%s", null, null, assistantName, "", "");
''' % (teacher_js, name, room, bits)
    for day, unit in cells:
        block += (
            "index = %d*unitCount+%d;\n"
            "table0.activities[index][table0.activities[index].length] = activity;\n"
        ) % (day, unit)
    return block


def make_activity(name="示例课程A", weeks=None, day=2, units=None, room="101"):
    return Activity(name, "SAMPLE", "教师甲", room,
                    [1, 2] if weeks is None else weeks, day,
                    [4, 5] if units is None else units)


class CourseParserTests(unittest.TestCase):
    def test_file_fixture_parses_exact_records(self):
        table = parse_course_table(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(table.unit_count, 12)
        self.assertEqual([vars(a) for a in table.activities], [
            dict(name="示例课程A", course_code="SECTION_A", teachers="教师甲、教师乙",
                 room="101", weeks=[1, 2], day=2, units=[4, 5]),
            dict(name="示例课程B", course_code="SECTION_B", teachers="",
                 room="", weeks=[3], day=0, units=[2]),
        ])

    def test_week_bitmap_indices_are_week_numbers(self):
        table = parse_course_table(make_block(bits="0110000000000000000000"))
        self.assertEqual(len(table), 1)
        self.assertEqual(table.activities[0].weeks, [1, 2])

    def test_week_zero_is_ignored_even_when_set(self):
        table = parse_course_table(make_block(bits="1110000000000000000000"))
        self.assertEqual(len(table), 1)
        self.assertEqual(table.activities[0].weeks, [1, 2])
        self.assertEqual(parse_course_table(make_block(bits="1000")).activities, [])

    def test_single_cell_uses_zero_based_day_and_unit(self):
        table = parse_course_table(make_block(cells=((2, 4),)))
        self.assertEqual(table.unit_count, 11)
        self.assertEqual([(a.day, a.units) for a in table.activities], [(2, [4])])

    def test_first_day_and_first_unit_are_zero(self):
        table = parse_course_table(make_block(cells=((0, 0),)))
        self.assertEqual([(a.day, a.units) for a in table.activities], [(0, [0])])

    def test_consecutive_cells_form_one_activity_in_unit_order(self):
        table = parse_course_table(make_block(cells=((2, 5), (2, 4))))
        self.assertEqual([(a.day, a.units) for a in table.activities], [(2, [4, 5])])

    def test_cells_on_different_days_form_separate_activities(self):
        table = parse_course_table(make_block(cells=((0, 4), (2, 5))))
        self.assertEqual([(a.day, a.units) for a in table.activities],
                         [(0, [4]), (2, [5])])

    def test_matching_records_merge_sorted_week_union(self):
        table = parse_course_table(
            make_block(bits="0011") + make_block(bits="0110")
        )
        self.assertEqual(len(table), 1)
        self.assertEqual(table.activities[0].weeks, [1, 2, 3])
        self.assertEqual(table.activities[0].units, [4])

    def test_different_rooms_do_not_merge(self):
        table = parse_course_table(make_block() + make_block(room="102", bits="0001"))
        self.assertEqual([(a.room, a.weeks) for a in table.activities],
                         [("101", [1, 2]), ("102", [3])])

    def test_different_teachers_do_not_merge(self):
        table = parse_course_table(
            make_block() + make_block(teachers=("教师乙",), bits="0001")
        )
        self.assertEqual([(a.teachers, a.weeks) for a in table.activities],
                         [("教师甲", [1, 2]), ("教师乙", [3])])

    def test_other_merge_key_fields_must_match(self):
        for changed in (
            dict(name="示例课程B"), dict(cells=((1, 4),)), dict(cells=((2, 5),)),
        ):
            with self.subTest(changed=changed):
                table = parse_course_table(make_block() + make_block(bits="0001", **changed))
                self.assertEqual(len(table), 2)
                self.assertEqual([a.weeks for a in table.activities], [[1, 2], [3]])

    def test_all_zero_bitmap_is_skipped(self):
        self.assertEqual(parse_course_table(make_block(bits="000000")).activities, [])

    def test_record_without_placement_is_skipped(self):
        self.assertEqual(parse_course_table(make_block(cells=())).activities, [])

    def test_empty_or_whitespace_course_name_is_skipped(self):
        for name in ("", "   "):
            with self.subTest(name=name):
                self.assertEqual(parse_course_table(make_block(name=name)).activities, [])

    def test_skipped_blocks_do_not_borrow_neighbor_cells(self):
        js = (make_block(name="示例课程B", cells=())
              + make_block(bits="0000") + make_block())
        table = parse_course_table(js)
        self.assertEqual([(a.name, a.weeks, a.day, a.units) for a in table.activities],
                         [("示例课程A", [1, 2], 2, [4])])

    def test_multiple_teachers_are_joined_with_separator(self):
        table = parse_course_table(make_block(teachers=("教师甲", "教师乙")))
        self.assertEqual(len(table), 1)
        self.assertEqual(table.activities[0].teachers, "教师甲、教师乙")

    def test_empty_teacher_array_produces_empty_string(self):
        table = parse_course_table(make_block(teachers=()))
        self.assertEqual(len(table), 1)
        self.assertEqual(table.activities[0].teachers, "")

    def test_unit_count_defaults_to_eleven(self):
        self.assertEqual(parse_course_table(make_block()).unit_count, 11)

    def test_explicit_unit_count_is_read(self):
        table = parse_course_table("var unitCount = 13;\n" + make_block(cells=((2, 12),)))
        self.assertEqual(table.unit_count, 13)
        self.assertEqual([(a.day, a.units) for a in table.activities], [(2, [12])])


class CourseTableTests(unittest.TestCase):
    def setUp(self):
        self.table = CourseTable()
        # Deliberately insert in reverse time order, with another day mixed in.
        self.table.add(make_activity("示例课程C", weeks=[2], units=[8, 9]))
        self.table.add(make_activity("示例课程D", day=1, units=[0]))
        self.table.add(make_activity("示例课程B", weeks=[1, 2], units=[4, 5]))
        self.table.add(make_activity("示例课程A", weeks=[1], units=[0, 1]))

    def test_on_day_sorts_by_unit_and_excludes_other_days(self):
        self.assertEqual([a.name for a in self.table.on_day(2)],
                         ["示例课程A", "示例课程B", "示例课程C"])
        self.assertEqual([a.units for a in self.table.on_day(2)],
                         [[0, 1], [4, 5], [8, 9]])

    def test_on_day_filters_week_and_keeps_unit_order(self):
        self.assertEqual([a.name for a in self.table.on_day(2, week=1)],
                         ["示例课程A", "示例课程B"])
        self.assertEqual([a.name for a in self.table.on_day(2, week=2)],
                         ["示例课程B", "示例课程C"])
        self.assertEqual(self.table.on_day(2, week=3), [])
        self.assertEqual(self.table.on_day(6), [])


class ActivityDisplayTests(unittest.TestCase):
    def test_compress_ranges(self):
        for numbers, expected in (
            ([5, 6, 7, 9, 10], "5-7,9-10"),
            ([10, 5, 9, 6, 5, 7], "5-7,9-10"), ([], ""), ([3], "3"),
        ):
            with self.subTest(numbers=numbers):
                self.assertEqual(_compress_ranges(numbers), expected)

    def test_unit_text_converts_zero_based_units(self):
        self.assertEqual(make_activity(units=[2]).unit_text, "3")
        self.assertEqual(make_activity(units=[4, 5]).unit_text, "5-6")
        self.assertEqual(make_activity(units=[]).unit_text, "")

    def test_room_text_handles_empty_room(self):
        self.assertEqual(make_activity(room="").room_text, "待定")
        self.assertEqual(make_activity(room="101").room_text, "101")

    def test_week_text_weekday_name_and_on_week(self):
        activity = make_activity(weeks=[5, 6, 7, 9, 10])
        self.assertEqual(activity.week_text, "5-7,9-10")
        self.assertEqual(activity.weekday_name, "三")
        self.assertTrue(activity.on_week(5))
        self.assertFalse(activity.on_week(8))


class PickSemesterTests(unittest.TestCase):
    # Latest year is intentionally neither first nor last in the text.
    SEMESTERS = '''semesters:{y0:[
        {id:11,schoolYear:"2030-2031",name:"1"},
        {id:12,schoolYear:"2030-2031",name:"2"}],y1:[
        {id:21,schoolYear:"2032-2033",name:"1"},
        {id:22,schoolYear:"2032-2033",name:"2"}],y2:[
        {id:31,schoolYear:"2031-2032",name:"1"},
        {id:32,schoolYear:"2031-2032",name:"2"}]}'''

    def test_march_selects_second_term_of_latest_year(self):
        today = datetime.date(2033, 3, 15)
        with patch("snut.course.datetime.date") as mock_date:
            mock_date.today.return_value = today
            self.assertEqual(_pick_semester(self.SEMESTERS), 22)
            mock_date.today.assert_called_once_with()

    def test_october_selects_first_term_of_latest_year(self):
        today = datetime.date(2032, 10, 15)
        with patch("snut.course.datetime.date") as mock_date:
            mock_date.today.return_value = today
            self.assertEqual(_pick_semester(self.SEMESTERS), 21)
            mock_date.today.assert_called_once_with()

    def test_no_semester_entries_returns_none(self):
        self.assertIsNone(_pick_semester("semesters:{}"))


if __name__ == "__main__":
    unittest.main()
