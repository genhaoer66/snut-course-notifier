import datetime
import unittest

from snut.formatter import current_week_from_start


class FormatterTests(unittest.TestCase):
    def test_current_week_uses_monday_as_week_one(self):
        start = datetime.date(2026, 8, 31)
        self.assertEqual(current_week_from_start(start, start), 1)
        self.assertEqual(current_week_from_start(start, start + datetime.timedelta(days=6)), 1)
        self.assertEqual(current_week_from_start(start, start + datetime.timedelta(days=7)), 2)

    def test_dates_before_start_are_week_one(self):
        start = datetime.date(2026, 8, 31)
        self.assertEqual(current_week_from_start(start, start - datetime.timedelta(days=1)), 1)
