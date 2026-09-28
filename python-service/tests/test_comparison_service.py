import unittest
from datetime import datetime, timezone

from app.schemas import BotCatalogItem, DailyPnlPoint, HistoricalReplayResponse, ResultsSummary
from app.services.comparison import build_equity_comparison


class ComparisonServiceTests(unittest.TestCase):
    def test_builds_cumulative_equity_and_reports_missing_profiles(self) -> None:
        available = BotCatalogItem(
            id="core-stochastic-v3", name="Stochastic Sell V3", description="",
            strategy_profile="stochastic_sell_v3_adaptive_shadow", symbol="XAUUSD", timeframe="M5",
        )
        missing = BotCatalogItem(
            id="core-stochastic-v4", name="Stochastic Sell V4", description="",
            strategy_profile="stochastic_sell_v4_retest_shadow", symbol="XAUUSD", timeframe="M5",
        )
        replay = HistoricalReplayResponse(
            bot_id=available.id, symbol="XAUUSD", timeframe="M5",
            period_start_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
            period_end_utc=datetime(2026, 1, 3, tzinfo=timezone.utc), candles_evaluated=2,
            candidates_detected=1, expectancy_r=.2, max_drawdown_r=1.0,
            summary=ResultsSummary(trades_count=2, net_pnl=3),
            daily_pnl=[DailyPnlPoint(day=datetime(2026, 1, 1).date(), net_pnl=5), DailyPnlPoint(day=datetime(2026, 1, 2).date(), net_pnl=-2)],
        )

        result = build_equity_comparison(
            [available, missing], symbol="XAUUSD", timeframe="M5", period_days=365,
            load_replay=lambda bot: replay if bot.id == available.id else None,
        )

        self.assertEqual([point.cumulative_pnl for point in result.series[0].points], [5, 3])
        self.assertEqual(result.missing_bot_ids, [missing.id])
        self.assertEqual(result.series[0].expectancy_r, .2)

    def test_orders_zigzag_series_by_public_taxonomy(self) -> None:
        later = BotCatalogItem(id="core-zigzag-v7", name="ZigZag Scalper V5.1", description="", strategy_profile="zigzag_scalper_v7_directional_shadow", symbol="XAUUSD", timeframe="M5")
        first = BotCatalogItem(id="core-zigzag", name="ZigZag Scalper V1.0", description="", strategy_profile="happy_gold_zigzag_scalper", symbol="XAUUSD", timeframe="M5")
        replay = HistoricalReplayResponse(
            bot_id=first.id, symbol="XAUUSD", timeframe="M5",
            period_start_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
            period_end_utc=datetime(2026, 1, 2, tzinfo=timezone.utc), candles_evaluated=1,
            candidates_detected=0,
            summary=ResultsSummary(), daily_pnl=[],
        )
        result = build_equity_comparison(
            [later, first], symbol="XAUUSD", timeframe="M5", period_days=365,
            load_replay=lambda bot: replay.model_copy(update={"bot_id": bot.id}),
        )

        self.assertEqual([series.bot_id for series in result.series], [first.id, later.id])


if __name__ == "__main__":
    unittest.main()
