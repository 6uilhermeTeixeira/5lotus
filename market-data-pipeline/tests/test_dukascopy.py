import datetime as dt
import lzma
import struct
import unittest

from lotus.ingestion.dukascopy import iter_hours, remote_path, validate_bi5, workers_for_batch


class DukascopyTest(unittest.TestCase):
    def test_workers_ramp_to_maximum(self):
        self.assertEqual([workers_for_batch(4, 8, batch) for batch in range(6)], [4, 5, 6, 7, 8, 8])

    def test_zero_based_month_path(self):
        hour = dt.datetime(2024, 1, 2, 3, tzinfo=dt.timezone.utc)
        self.assertEqual(remote_path("XAUUSD", hour), "XAUUSD/2024/00/02/03h_ticks.bi5")

    def test_inclusive_date_hours(self):
        hours = list(iter_hours(dt.date(2024, 1, 1), dt.date(2024, 1, 1)))
        self.assertEqual(len(hours), 24)

    def test_bi5_validation(self):
        raw = struct.pack(">IIIff", 123, 200_001, 200_000, 1.5, 2.5)
        count, first, last = validate_bi5(lzma.compress(raw))
        self.assertEqual((count, first, last), (1, 123, 123))


if __name__ == "__main__":
    unittest.main()
