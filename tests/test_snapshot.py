import datetime
import json
import tempfile
import unittest
from types import SimpleNamespace

from snut.course import Activity, CourseTable
from snut.snapshot import build_snapshot, load_snapshot, save_snapshot


def make_config(tmp_path):
    return SimpleNamespace(
        semester_start=datetime.date(2026, 8, 31),
        data_dir=tmp_path,
        ensure_dirs=lambda: tmp_path.mkdir(parents=True, exist_ok=True),
    )


class SnapshotTests(unittest.TestCase):
    def test_snapshot_exports_only_public_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            from pathlib import Path

            tmp_path = Path(folder)
            table = CourseTable(semester_id=162, unit_count=11)
            activity = Activity(
                "工程制图", "PRIVATE-COURSE-CODE", "教师 A", "A203", [1, 2], 0, [0, 1]
            )
            activity.private_student_id = "must-not-leak"
            table.add(activity)

            payload = build_snapshot(
                table, make_config(tmp_path), now=datetime.datetime(2026, 9, 25, 8, 30)
            )

            self.assertEqual(set(payload), {
                "updated_at", "updated_ts", "semester_start", "unit_count", "periods", "courses"
            })
            self.assertEqual(set(payload["courses"][0]), {
                "name", "teachers", "room", "day", "units", "weeks"
            })
            self.assertNotIn("PRIVATE-COURSE-CODE", json.dumps(payload))
            self.assertNotIn("must-not-leak", json.dumps(payload))

    def test_snapshot_write_is_readable(self):
        with tempfile.TemporaryDirectory() as folder:
            from pathlib import Path

            tmp_path = Path(folder)
            table = CourseTable(unit_count=11)
            table.add(Activity("车辆动力学", "C1", "教师 B", "B407", [4], 4, [6, 7]))
            config = make_config(tmp_path)
            path = save_snapshot(table, config, now=datetime.datetime(2026, 9, 25, 8, 30))

            self.assertEqual(path.name, "timetable.json")
            self.assertEqual(load_snapshot(config)["courses"][0]["name"], "车辆动力学")
            self.assertFalse((tmp_path / "timetable.json.tmp").exists())
