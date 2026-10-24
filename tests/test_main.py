import datetime
import importlib
import io
import unittest
from contextlib import ExitStack, redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

with patch('dotenv.load_dotenv'):
    main = importlib.import_module('snut.main')

from snut.course import Activity, CourseTable


class FixedDate(datetime.date):
    @classmethod
    def today(cls):
        return cls(2026, 9, 7)


class MainTests(unittest.TestCase):
    def test_resolve_week(self):
        config = SimpleNamespace(semester_start=datetime.date(2026, 8, 31))
        for target, override, expected in [(datetime.date(2026, 8, 30), None, 1),
                                            (datetime.date(2026, 9, 7), None, 2),
                                            (datetime.date(2026, 9, 7), 9, 9)]:
            self.assertEqual(main.resolve_week(config, target, override), expected)
        config.semester_start = None
        self.assertIsNone(main.resolve_week(config, datetime.date(2026, 9, 7)))
        self.assertEqual(main.resolve_week(config, datetime.date(2026, 9, 7), 4), 4)

    def test_parser(self):
        parser = main.build_parser()
        self.assertEqual(vars(parser.parse_args([])), dict(target='today', week=None,
                         dry_run=False, no_snapshot=False, verbose=False))
        self.assertEqual(vars(parser.parse_args(['--for', 'tomorrow', '--week', '9',
                         '--dry-run', '--no-snapshot', '-v'])), dict(target='tomorrow',
                         week=9, dry_run=True, no_snapshot=True, verbose=True))
        self.assertTrue(parser.parse_args(['--verbose']).verbose)
        for args in (['--for', 'yesterday'], ['--week', 'bad']):
            with self.subTest(args=args), patch('sys.stderr', new_callable=io.StringIO):
                with self.assertRaises(SystemExit) as caught:
                    parser.parse_args(args)
                self.assertEqual(caught.exception.code, 2)

    def test_dry_run_prints_without_push_or_external_io(self):
        config = SimpleNamespace(semester_start=datetime.date(2026, 8, 31), mail_enabled=True)
        table = CourseTable()
        table.add(Activity('合成课程', 'PRIVATE', '教师甲', 'A101', [2], 0, [0, 1]))
        for extra in ([], ['--no-snapshot'], ['--for', 'tomorrow', '--week', '9']):
            with self.subTest(extra=extra), ExitStack() as stack:
                get_config = stack.enter_context(patch.object(main, 'get_config', return_value=config))
                logging = stack.enter_context(patch.object(main, 'setup_logging'))
                login = stack.enter_context(patch.object(main, 'LoginClient'))
                solver = stack.enter_context(patch.object(main, 'CaptchaSolver'))
                fetch = stack.enter_context(patch.object(main, 'load_course_table', return_value=table))
                snapshot = stack.enter_context(patch.object(main, 'save_snapshot'))
                push = stack.enter_context(patch.object(main, 'push'))
                alert = stack.enter_context(patch.object(main, 'send_alert'))
                stack.enter_context(patch.object(main.datetime, 'date', FixedDate))
                output = stack.enter_context(redirect_stdout(io.StringIO()))
                self.assertEqual(main.main(['--dry-run'] + extra), 0)
                get_config.assert_called_once_with()
                logging.assert_called_once_with(config, False)
                login.assert_called_once_with(config)
                login.return_value.ensure_login.assert_called_once_with(solver=solver.return_value)
                fetch.assert_called_once_with(login.return_value)
                push.assert_not_called()
                alert.assert_not_called()
                if '--no-snapshot' in extra:
                    snapshot.assert_not_called()
                else:
                    snapshot.assert_called_once_with(table, config)
                if '--for' in extra:
                    expected = '\n明日课表 | 9月8日 星期二 · 第9周\n' + '-' * 34 + '\n\n今天没有课，好好休息 ~\n\n'
                else:
                    expected = ('\n今日课表 | 9月7日 星期一 · 第2周\n' + '-' * 34 +
                                '\n共 1 门课\n\n第 1-2 节  合成课程\n    教室：A101\n'
                                '    教师：教师甲\n    周次：2\n\n')
                self.assertEqual(output.getvalue(), expected)
