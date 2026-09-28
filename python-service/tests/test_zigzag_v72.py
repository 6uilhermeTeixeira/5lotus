import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.strategies import zigzag_v72


class V72Tests(unittest.TestCase):
    def test_weekday_release_set_is_wednesday_and_thursday_utc(self):
        self.assertIn(datetime(2026, 1, 7, tzinfo=timezone.utc).weekday(), zigzag_v72.V3_RELEASE_WEEKDAYS)
        self.assertIn(datetime(2026, 1, 8, tzinfo=timezone.utc).weekday(), zigzag_v72.V3_RELEASE_WEEKDAYS)
        self.assertNotIn(datetime(2026, 1, 9, tzinfo=timezone.utc).weekday(), zigzag_v72.V3_RELEASE_WEEKDAYS)
