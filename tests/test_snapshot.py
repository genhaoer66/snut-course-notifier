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
            activity.ids = "private-internal-id"
            activity.username = "private-username"
            activity.password = "private-password"
            activity.smtp_auth_code = "private-auth-code"
            activity.semester_id = "private-semester-id"
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
            self.assertEqual(payload["courses"][0], {
                "name": "工程制图", "teachers": "教师 A", "room": "A203",
                "day": 0, "units": [0, 1], "weeks": [1, 2],
            })
            for secret in ("private-internal-id", "private-username", "private-password",
                           "private-auth-code", "private-semester-id"):
                self.assertNotIn(secret, json.dumps(payload))
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

from pathlib import Path
from unittest.mock import patch


class SnapshotFailureTests(unittest.TestCase):
    def test_partial_write_preserves_old_snapshot_and_does_not_replace(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_config(Path(folder))
            target = config.data_dir / 'timetable.json'
            old = b'{"courses":[],"marker":"old"}'
            target.write_bytes(old)
            original_write = Path.write_text

            def partial_write(path, text, **kwargs):
                original_write(path, text[:10], **kwargs)
                raise OSError('synthetic disk full')

            with patch.object(Path, 'write_text', partial_write), \
                    patch('snut.snapshot.os.replace') as replace:
                with self.assertRaisesRegex(OSError, 'disk full'):
                    save_snapshot(CourseTable(), config)
                replace.assert_not_called()
            self.assertEqual(target.read_bytes(), old)
            self.assertEqual(load_snapshot(config), {'courses': [], 'marker': 'old'})

    def test_partial_write_does_not_publish_new_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_config(Path(folder))
            original_write = Path.write_text

            def partial_write(path, text, **kwargs):
                original_write(path, text[:10], **kwargs)
                raise OSError('synthetic disk full')

            with patch.object(Path, 'write_text', partial_write):
                with self.assertRaises(OSError):
                    save_snapshot(CourseTable(), config)
            self.assertFalse((config.data_dir / 'timetable.json').exists())

    def test_replace_failure_preserves_old_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_config(Path(folder))
            target = save_snapshot(CourseTable(), config)
            old = target.read_bytes()
            table = CourseTable()
            table.add(Activity('new', 'PRIVATE', 'teacher', 'room', [1], 0, [0]))
            with patch('snut.snapshot.os.replace', side_effect=OSError('replace failed')):
                with self.assertRaisesRegex(OSError, 'replace failed'):
                    save_snapshot(table, config)
            self.assertEqual(target.read_bytes(), old)

    def test_replace_receives_complete_payload_and_permissions_precede_publish(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_config(Path(folder))
            table = CourseTable()
            table.add(Activity('public', 'PRIVATE', 'teacher', 'room', [1], 0, [0]))
            import os
            real_replace = os.replace

            def replace(source, target):
                self.assertEqual(json.loads(source.read_text(encoding='utf-8'))['courses'][0]['name'], 'public')
                chmod.assert_called_once_with(source, 0o600)
                real_replace(source, target)

            with patch('snut.snapshot.os.chmod') as chmod, \
                    patch('snut.snapshot.os.replace', side_effect=replace):
                save_snapshot(table, config)
            self.assertFalse((config.data_dir / 'timetable.json.tmp').exists())
