import unittest
from datetime import datetime, timezone

from app.strategies.zigzag_v8 import calendar_allows, week_of_month


class V8Tests(unittest.TestCase):
    def test_accuracy_cycle_calendar(self):
        self.assertEqual(week_of_month(datetime(2026, 1, 12, tzinfo=timezone.utc)), 2)  # Monday
        self.assertTrue(calendar_allows(datetime(2026, 1, 12, tzinfo=timezone.utc), "sell"))
        self.assertTrue(calendar_allows(datetime(2026, 1, 20, tzinfo=timezone.utc), "buy"))  # Tue, week 3
        self.assertFalse(calendar_allows(datetime(2026, 1, 20, tzinfo=timezone.utc), "sell"))
        self.assertTrue(calendar_allows(datetime(2026, 1, 23, tzinfo=timezone.utc), "sell"))  # Fri, week 4
        self.assertFalse(calendar_allows(datetime(2026, 1, 5, tzinfo=timezone.utc), "buy"))
