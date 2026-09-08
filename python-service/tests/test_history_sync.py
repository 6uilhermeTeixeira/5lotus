import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import duckdb

from app.history_sync import load_tick_indicators, refresh_history
from app.schemas import BotCatalogItem, CandleSnapshot, HistoricalReplayResponse, ResultsSummary


class HistorySyncTests(unittest.TestCase):
    def test_tick_indicators_use_only_prices_available_at_candle_close(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            parquet = root / "seconds.parquet"
            connection = duckdb.connect(":memory:")
            connection.execute(
                "COPY (SELECT * FROM (VALUES (0, 100.0), (270000, 101.0), (299999, 104.0), (300999, 999.0)) t(t,c)) TO ? (FORMAT PARQUET)",
                [str(parquet)],
            )
            connection.close()
            candle = CandleSnapshot(
                timestamp_utc=datetime(1970, 1, 1, tzinfo=timezone.utc),
                open=100, high=105, low=99, close=104, volume=3,
            )
            release = SimpleNamespace(
                root=root,
                manifest={
                    "instrument": "XAUUSD",
                    "aggregations": {"1s": [{"day": "1970-01-01", "path": "seconds.parquet"}]},
                },
            )

            result = load_tick_indicators(release, "XAUUSD", [candle])

            features = result[300_000]
            self.assertEqual(features["impulse_30s_ready"], 1.0)
            self.assertEqual(features["impulse_30s_move_points"], 300.0)
            self.assertEqual(features["impulse_300s_ready"], 1.0)
            self.assertEqual(features["impulse_300s_move_points"], 400.0)

    @patch("app.history_sync.run_historical_replay")
    @patch("app.history_sync.SupabaseStore")
    @patch("app.history_sync.load_m5_candles")
    @patch("app.history_sync.DatasetRelease.open")
    @patch("app.history_sync.publish_downloaded_history")
    def test_refresh_imports_candles_and_updates_each_active_snapshot(
        self, publish, open_release, load_candles, store_class, run_replay
    ) -> None:
        timestamp = datetime(2026, 9, 1, tzinfo=timezone.utc)
        candle = CandleSnapshot(timestamp_utc=timestamp, open=1, high=2, low=1, close=2, volume=3)
        bot = BotCatalogItem(id="bot-1", name="Bot", description="Teste", strategy_profile="test", symbol="XAUUSD", timeframe="M5")
        release = SimpleNamespace(version="release-1", manifest={"collection": {"progress_pct": 12.5}})
        replay = HistoricalReplayResponse(
            bot_id=bot.id, symbol=bot.symbol, timeframe=bot.timeframe,
            period_start_utc=timestamp, period_end_utc=timestamp,
            candles_evaluated=1, candidates_detected=0, summary=ResultsSummary(),
        )
        settings = SimpleNamespace(lotus_data_root="/data", results_store="SUPABASE")
        store = MagicMock()
        store.list_bots.return_value = [bot]
        open_release.return_value = release
        load_candles.return_value = [candle]
        store_class.return_value = store
        run_replay.return_value = replay

        result = refresh_history(settings, days=365)

        publish.assert_called_once_with(settings, "XAUUSD", 365)
        store.upsert_candles.assert_called_once_with("bot-1", "XAUUSD", "M5", [candle])
        store.save_backtest_snapshot.assert_called_once_with(replay, 365)
        self.assertEqual(result.snapshots_updated, 1)
        self.assertEqual(result.candles_imported, 1)
        self.assertEqual(result.collection_progress_pct, 12.5)


if __name__ == "__main__":
    unittest.main()
