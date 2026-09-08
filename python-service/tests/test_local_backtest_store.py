import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app.local_backtest_store import load_local_backtest, save_local_backtest
from app.schemas import CandleSnapshot, HistoricalReplayResponse, ResultsSummary


class LocalBacktestStoreTests(unittest.TestCase):
    def test_snapshot_is_atomic_compact_and_round_trips(self) -> None:
        timestamp = datetime(2026, 9, 1, tzinfo=timezone.utc)
        replay = HistoricalReplayResponse(
            bot_id="bot-1", symbol="XAUUSD", timeframe="M5",
            period_start_utc=timestamp, period_end_utc=timestamp,
            candles_evaluated=1, candidates_detected=0, summary=ResultsSummary(),
            candles=[CandleSnapshot(timestamp_utc=timestamp, open=1, high=2, low=1, close=2, volume=3)],
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save_local_backtest(root, replay, 365)
            loaded = load_local_backtest(root, "bot-1", 365)

            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.bot_id, "bot-1")
            self.assertEqual(loaded.candles, [])
            self.assertEqual(list(root.glob("*.part")), [])


if __name__ == "__main__":
    unittest.main()
