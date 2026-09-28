import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app import main
from app.local_dataset import DatasetError
from app.schemas import BotCatalogItem, EquitySeries, HistoricalReplayResponse, ResultsSummary, TradeResult
from app.supabase_store import SupabaseRequestError


class ResultsReplayEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bot = BotCatalogItem(
            id="core-zigzag-v3", name="ZigZag V3", description="Teste",
            strategy_profile="zigzag_scalper_v3_adaptive_shadow", symbol="XAUUSD", timeframe="M5",
        )
        self.timestamp = datetime(2026, 9, 1, tzinfo=timezone.utc)
        self.replay = HistoricalReplayResponse(
            bot_id=self.bot.id, symbol="XAUUSD", timeframe="M5",
            period_start_utc=datetime(2025, 9, 1, tzinfo=timezone.utc),
            period_end_utc=self.timestamp, candles_evaluated=100, candidates_detected=1,
            summary=ResultsSummary(),
            trades=[TradeResult(
                trade_id="trade-1", symbol="XAUUSD", timeframe="M5", setup="test", side="buy",
                opened_at_utc=self.timestamp, closed_at_utc=self.timestamp, volume_lots=.1,
                entry_price=100, exit_price=101, net_pnl=25, rr_realized=1,
            )],
        )

    @patch("app.main.load_chart_candles")
    @patch("app.main.DatasetRelease.open")
    @patch("app.main._load_cached_backtest")
    def test_local_historical_replay_returns_cached_results_and_dataset_candles(
        self, load_backtest, open_release, load_candles
    ) -> None:
        load_backtest.return_value = self.replay
        load_candles.return_value = [SimpleNamespace(t=1_788_192_000_000, o=100, h=102, l=99, c=101, volume=7)]

        with patch("app.main._require_api_session"), patch("app.main._find_bot", return_value=self.bot), patch("app.main._uses_supabase_results", return_value=False):
            result = main.read_historical_replay(self.bot.id, MagicMock(), 365)

        self.assertEqual(result.summary.net_pnl, 0)
        self.assertEqual(len(result.trades), 1)
        self.assertEqual(len(result.candles), 1)
        self.assertEqual(result.candles[0].close, 101)
        open_release.assert_called_once()
        load_candles.assert_called_once()

    @patch("app.main._load_cached_backtest")
    def test_short_period_is_derived_from_annual_cache(self, load_backtest) -> None:
        load_backtest.side_effect = [None, self.replay]
        with patch("app.main.DatasetRelease.open"), patch("app.main.load_chart_candles", return_value=[]):
            result = main._load_local_replay_with_candles(self.bot, 30)

        self.assertIsNotNone(result)
        self.assertEqual(result.summary.net_pnl, 25)
        self.assertEqual(result.summary.trades_count, 1)
        self.assertEqual(result.period_start_utc.date().isoformat(), "2026-08-02")

    @patch("app.main._load_cached_backtest")
    def test_normalized_comparison_restarts_risk_inside_selected_period(self, load_backtest) -> None:
        load_backtest.side_effect = [None, None, self.replay]

        result = main._load_comparison_replay(self.bot, 90, "normalized")

        self.assertIsNotNone(result)
        self.assertEqual(result.risk_per_trade_pct, 1)
        self.assertEqual(result.summary.net_pnl, 100)
        self.assertEqual(result.trades[0].risk_amount, 100)

    def test_market_chart_keeps_equity_when_dataset_is_unavailable(self) -> None:
        equity = SimpleNamespace(
            series=[EquitySeries(bot_id=self.bot.id, name=self.bot.name, strategy_profile=self.bot.strategy_profile, summary=ResultsSummary(), points=[])],
            missing_bot_ids=[],
        )
        with patch("app.main._require_api_session"), patch("app.main._build_equity_comparison", return_value=equity), patch(
            "app.main.DatasetRelease.open", side_effect=DatasetError("dataset não montado")
        ):
            result = main.read_backtest_market_chart(MagicMock(), days=365)

        self.assertEqual(result.dataset_version, "unavailable")
        self.assertEqual(result.candles, [])
        self.assertEqual([item.bot_id for item in result.series], [self.bot.id])

    def test_supabase_cache_falls_back_to_bundled_snapshot(self) -> None:
        store = MagicMock()
        store.load_backtest_snapshot.return_value = None
        with patch("app.main._uses_supabase_results", return_value=True), patch(
            "app.main.SupabaseStore", return_value=store
        ), patch("app.main.load_local_backtest", return_value=self.replay) as local:
            result = main._load_cached_backtest(self.bot, 365, "normalized")

        self.assertIs(result, self.replay)
        local.assert_called_once_with(main.settings.backtest_cache_path, self.bot.id, 365)

    def test_transient_supabase_failure_falls_back_to_bundled_snapshot(self) -> None:
        store = MagicMock()
        store.load_backtest_snapshot.side_effect = SupabaseRequestError(
            "temporarily unavailable", code="http_error", retryable=True, status_code=503
        )
        with patch("app.main._uses_supabase_results", return_value=True), patch(
            "app.main.SupabaseStore", return_value=store
        ), patch("app.main.load_local_backtest", return_value=self.replay) as local:
            result = main._load_cached_backtest(self.bot, 365, "normalized")

        self.assertIs(result, self.replay)
        local.assert_called_once_with(main.settings.backtest_cache_path, self.bot.id, 365)

    def test_supabase_auth_failure_does_not_hide_behind_local_snapshot(self) -> None:
        store = MagicMock()
        store.load_backtest_snapshot.side_effect = SupabaseRequestError(
            "unauthorized", code="auth_error", retryable=False, status_code=401
        )
        with patch("app.main._uses_supabase_results", return_value=True), patch(
            "app.main.SupabaseStore", return_value=store
        ), patch("app.main.load_local_backtest", return_value=self.replay) as local:
            with self.assertRaises(SupabaseRequestError):
                main._load_cached_backtest(self.bot, 365, "normalized")

        local.assert_not_called()

    def test_supabase_mode_uses_versioned_catalog_instead_of_stale_remote_rows(self) -> None:
        catalog = [self.bot]
        with patch("app.main._uses_supabase_results", return_value=True), patch(
            "app.main.load_bots_catalog", side_effect=[catalog, []]
        ), patch("app.main.SupabaseStore.list_bots") as remote:
            result = main._list_bots()

        self.assertEqual(result, catalog)
        remote.assert_not_called()

    def test_legacy_quarter_percent_replay_is_normalized_for_comparison(self) -> None:
        self.replay.risk_per_trade_pct = 0.25
        with patch("app.main._load_cached_backtest", return_value=self.replay):
            result = main._load_comparison_replay(self.bot, 365, "normalized")

        self.assertEqual(result.risk_per_trade_pct, 1.0)
        self.assertEqual(result.trades[0].risk_amount, 100.0)


if __name__ == "__main__":
    unittest.main()
