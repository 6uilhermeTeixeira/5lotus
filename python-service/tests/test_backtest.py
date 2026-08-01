import unittest
from datetime import datetime, timedelta, timezone

from app.backtest import _OpenTrade, _advance_trade, run_historical_replay
from app.schemas import BotCatalogItem, CandleSnapshot
from tests.test_strategy import macd_trend_request, settings


def replay_settings():
    configured = settings()
    configured.backtest_balance = 10_000
    configured.backtest_spread_points = 10
    configured.backtest_point_size = 0.01
    configured.backtest_value_per_point_per_lot = 1
    configured.backtest_risk_per_trade_pct = 0.25
    configured.backtest_slippage_points = 0
    configured.backtest_commission_per_lot = 0
    configured.backtest_session_start_utc = "06:00"
    configured.backtest_session_end_utc = "21:00"
    configured.backtest_max_trades_per_day = 4
    configured.backtest_daily_loss_limit_r = 2
    configured.backtest_cooldown_bars_after_loss = 3
    configured.backtest_regime_enabled = False
    configured.backtest_validation_fold_days = 5
    return configured


class HistoricalReplayTests(unittest.TestCase):
    def test_replay_detects_signal_without_using_future_candle(self) -> None:
        request = macd_trend_request(datetime(2026, 7, 31, 10, 20, tzinfo=timezone.utc))
        bot = BotCatalogItem(
            id="bot-4",
            name="MACD",
            description="Teste",
            strategy_profile="macd_trend_crossover",
            symbol="XAUUSD",
            timeframe="M5",
        )

        result = run_historical_replay(bot, request.candles, replay_settings())

        self.assertEqual(result.candidates_detected, 1)
        self.assertEqual(result.candidates_eligible, 1)
        self.assertEqual(result.summary.trades_count, 1)
        self.assertEqual(result.summary.open_positions, 0)
        self.assertEqual(result.forced_session_closes, 1)
        self.assertEqual(result.validation_status, "insufficient_history")
        self.assertEqual(result.trades[0].opened_at_utc, request.candles[-1].timestamp_utc + timedelta(minutes=5))

    def test_stop_precedes_targets_when_same_candle_touches_both(self) -> None:
        opened_at = datetime(2026, 7, 31, 10, 0, tzinfo=timezone.utc)
        trade = _OpenTrade(
            trade_id="replay-1",
            setup="test",
            symbol="XAUUSD",
            timeframe="M5",
            side="buy",
            opened_at_utc=opened_at,
            volume_lots=1,
            entry_price=100,
            initial_stop_price=99,
            stop_price=100,
            partial_price=101,
            target_price=102,
            risk_amount=100,
            remaining_fraction=0.5,
            realized_gross_pnl=50,
            partial_hit=True,
        )
        candle = CandleSnapshot(
            timestamp_utc=opened_at + timedelta(minutes=5),
            open=100,
            high=103,
            low=99,
            close=102,
            volume=100,
        )

        result = _advance_trade(trade, candle, replay_settings())

        self.assertIsNotNone(result)
        self.assertEqual(result.rr_realized, 0.5)
        self.assertEqual(result.exit_price, 100)
        self.assertEqual(result.net_pnl, 50)

    def test_sell_stop_is_checked_against_historical_ask(self) -> None:
        configured = replay_settings()
        configured.backtest_spread_points = 10
        opened_at = datetime(2026, 7, 31, 10, 0, tzinfo=timezone.utc)
        trade = _OpenTrade(
            trade_id="sell-1",
            setup="test",
            symbol="XAUUSD",
            timeframe="M5",
            side="sell",
            opened_at_utc=opened_at,
            volume_lots=1,
            entry_price=100,
            initial_stop_price=101,
            stop_price=101,
            partial_price=99,
            target_price=98,
            risk_amount=100,
        )
        candle = CandleSnapshot(
            timestamp_utc=opened_at + timedelta(minutes=5),
            open=100,
            high=100.95,
            low=99.5,
            close=100,
            volume=100,
        )

        result = _advance_trade(trade, candle, configured)

        self.assertIsNotNone(result)
        self.assertEqual(result.exit_price, 101)
        self.assertLess(result.net_pnl, 0)


if __name__ == "__main__":
    unittest.main()
