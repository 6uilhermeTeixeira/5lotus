import datetime as dt
import lzma
from pathlib import Path
import struct
import tempfile
import unittest

from lotus.data.market import Tick, aggregate_ticks, choose_resolution, decode_bi5, serialize_ticks


class MarketDataTest(unittest.TestCase):
    def test_decodes_dukascopy_ask_bid_and_scale(self):
        raw = struct.pack(">IIIff", 125, 2_000_250, 2_000_000, 1.5, 2.5)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "00h_ticks.bi5"
            path.write_bytes(lzma.compress(raw))
            tick = list(decode_bi5(path, 1_000_000))[0]
        self.assertEqual(tick.timestamp_ms, 1_000_125)
        self.assertEqual((tick.bid, tick.ask), (2000.0, 2000.25))
        self.assertAlmostEqual(tick.bid_volume, 2.5)
        self.assertAlmostEqual(tick.ask_volume, 1.5)

    def test_ohlc_uses_semiopen_utc_buckets(self):
        ticks = [
            Tick(1_000, 9, 11, 2, 3),
            Tick(1_500, 11, 13, 5, 7),
            Tick(2_000, 7, 9, 1, 1),
        ]
        rows = aggregate_ticks(ticks, "1s", "mid")
        self.assertEqual(len(rows), 2)
        self.assertEqual((rows[0]["o"], rows[0]["h"], rows[0]["l"], rows[0]["c"]), (10, 12, 10, 12))
        self.assertEqual(rows[0]["tick_count"], 2)
        self.assertEqual(rows[0]["bid_volume"], 7)

    def test_auto_resolution_obeys_pixel_density(self):
        self.assertEqual(choose_resolution(0, 86_400_000, 1_000, "auto"), "5m")
        self.assertEqual(choose_resolution(0, 1_000, 1_000, "auto"), "1s")

    def test_tick_serialization_coalesces_equal_milliseconds(self):
        rows, truncated = serialize_ticks([
            Tick(1_000, 9, 10, 1, 2), Tick(1_000, 10, 11, 3, 4), Tick(1_001, 11, 12, 5, 6),
        ])
        self.assertFalse(truncated)
        self.assertEqual([row["t"] for row in rows], [1_000, 1_001])
        self.assertEqual((rows[0]["bid"], rows[0]["ask"]), (10, 11))
        self.assertEqual((rows[0]["bid_volume"], rows[0]["ask_volume"]), (4, 6))


if __name__ == "__main__":
    unittest.main()
