import unittest
from collections import deque
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.schemas import AccountSnapshot, CandleSnapshot, DecisionAction, DecisionRequest, FlowSnapshot, OrderBookLevel
from app.strategy import FlowSample, _flow_analysis, evaluate_decision, reset_strategy_state


def settings(**overrides: object) -> SimpleNamespace:
    values = {
        "default_symbol": "XAUUSD",
        "default_timeframe": "M5",
        "max_spread_points": 50.0,
        "risk_per_trade_pct": 1.0,
        "strategy_profile": "fimath_ema20_flow",
        "fimath_flow_window_seconds": 300,
        "fimath_flow_min_samples": 30,
        "fimath_flow_z_threshold": 1.0,
        "fimath_flow_policy": "veto",
        "fimath_mode": "shadow",
        "enable_live_decisions": False,
        "fimath_partial_pct": 50.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def bullish_request(timestamp: datetime, ask: float = 102.1) -> DecisionRequest:
    candles = []
    for index in range(22):
        close = 100 + index * 0.1
        candles.append(
            CandleSnapshot(
                timestamp_utc=timestamp - timedelta(minutes=(22 - index) * 5),
                open=close - 0.05,
                high=close + 0.25,
                low=close - 0.25,
                close=close,
                volume=100,
            )
        )
    candles.append(
        CandleSnapshot(
            timestamp_utc=timestamp,
            open=101.7,
            high=102.3,
            low=100.7,
            close=102.0,
            volume=120,
        )
    )
    return DecisionRequest(
        bot_id="bot-1",
        request_id=f"request-{timestamp.timestamp()}",
        timestamp_utc=timestamp + timedelta(seconds=5),
        symbol="XAUUSD",
        timeframe="M5",
        bid=102.0,
        ask=ask,
        spread_points=10,
        point_size=0.01,
        value_per_point_per_lot=1,
        candles=candles,
        positions=[],
        account=AccountSnapshot(balance=10_000, equity=10_000, margin_free=10_000),
        flow=FlowSnapshot(
            book=[
                OrderBookLevel(side="bid", price=102, volume=100),
                OrderBookLevel(side="ask", price=102.1, volume=100),
            ],
            up_ticks=2,
            down_ticks=1,
            up_volume=2,
            down_volume=1,
        ),
    )


def momentum_request(timestamp: datetime) -> DecisionRequest:
    candles = []
    for index in range(51):
        close = 100 + index * 0.08
        candles.append(
            CandleSnapshot(
                timestamp_utc=timestamp - timedelta(minutes=(52 - index) * 5),
                open=close - 0.03,
                high=close + 0.12,
                low=close - 0.12,
                close=close,
                volume=100,
            )
        )
    previous_high = max(candle.high for candle in candles[-12:])
    candles.append(
        CandleSnapshot(
            timestamp_utc=timestamp,
            open=previous_high - 0.05,
            high=previous_high + 0.35,
            low=previous_high - 0.10,
            close=previous_high + 0.25,
            volume=130,
        )
    )
    return DecisionRequest(
        bot_id="bot-2",
        request_id=f"momentum-{timestamp.timestamp()}",
        timestamp_utc=timestamp + timedelta(seconds=5),
        symbol="XAUUSD",
        timeframe="M5",
        bid=candles[-1].close,
        ask=candles[-1].close + 0.1,
        spread_points=10,
        point_size=0.01,
        value_per_point_per_lot=1,
        candles=candles,
        positions=[],
        account=AccountSnapshot(balance=10_000, equity=10_000, margin_free=10_000),
    )


def mean_reversion_request(timestamp: datetime) -> DecisionRequest:
    candles = []
    for index in range(21):
        close = 103 - index * 0.15
        candles.append(
            CandleSnapshot(
                timestamp_utc=timestamp - timedelta(minutes=(22 - index) * 5),
                open=close + 0.05,
                high=close + 0.20,
                low=close - 0.20,
                close=close,
                volume=100,
            )
        )
    candles.append(
        CandleSnapshot(
            timestamp_utc=timestamp,
            open=99.0,
            high=100.4,
            low=97.0,
            close=100.2,
            volume=140,
        )
    )
    return DecisionRequest(
        bot_id="bot-3",
        request_id=f"mean-reversion-{timestamp.timestamp()}",
        timestamp_utc=timestamp + timedelta(seconds=5),
        symbol="XAUUSD",
        timeframe="M5",
        bid=100.2,
        ask=100.3,
        spread_points=10,
        point_size=0.01,
        value_per_point_per_lot=1,
        candles=candles,
        positions=[],
        account=AccountSnapshot(balance=10_000, equity=10_000, margin_free=10_000),
    )


class FlowAnalysisTests(unittest.TestCase):
    def test_strong_directional_flow_is_confirmed(self) -> None:
        start = datetime(2026, 7, 31, tzinfo=timezone.utc)
        samples = deque(
            FlowSample(start + timedelta(seconds=index * 10), (index % 3 - 1) * 0.01, (index % 5 - 2) * 0.01)
            for index in range(30)
        )
        samples.append(FlowSample(start + timedelta(seconds=300), 0.8, 0.8))

        result = _flow_analysis(samples, DecisionAction.BUY, 300, 30, 1.0)

        self.assertTrue(result.ready)
        self.assertTrue(result.confirmed)
        self.assertFalse(result.contradicted)
        self.assertEqual(result.status, "aggression")

    def test_strong_opposing_flow_vetoes_candidate(self) -> None:
        start = datetime(2026, 7, 31, tzinfo=timezone.utc)
        samples = deque(
            FlowSample(start + timedelta(seconds=index * 10), (index % 3 - 1) * 0.01, (index % 5 - 2) * 0.01)
            for index in range(30)
        )
        samples.append(FlowSample(start + timedelta(seconds=300), -0.8, -0.8))

        result = _flow_analysis(samples, DecisionAction.BUY, 300, 30, 1.0)

        self.assertTrue(result.ready)
        self.assertFalse(result.confirmed)
        self.assertTrue(result.contradicted)
        self.assertEqual(result.status, "flow_contradiction")


class DecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_strategy_state()

    def test_warmup_candidate_keeps_prices_and_telemetry(self) -> None:
        request = bullish_request(datetime(2026, 7, 31, 10, 20, tzinfo=timezone.utc))

        response = evaluate_decision(request, settings())

        self.assertEqual(response.action, DecisionAction.HOLD)
        self.assertEqual(response.reason, "flow_warmup")
        self.assertTrue(response.metadata["candidate"])
        self.assertEqual(response.metadata["suggested_action"], "buy")
        self.assertIsNotNone(response.entry_price)
        self.assertIsNotNone(response.stop_loss_price)

    def test_setup_is_evaluated_once_per_closed_candle(self) -> None:
        candle_time = datetime(2026, 7, 31, 10, 20, tzinfo=timezone.utc)
        first = evaluate_decision(bullish_request(candle_time, ask=102.1), settings())
        second_request = bullish_request(candle_time, ask=105.0)
        second_request.timestamp_utc += timedelta(seconds=5)

        second = evaluate_decision(second_request, settings())

        self.assertEqual(first.entry_price, 102.1)
        self.assertEqual(second.entry_price, first.entry_price)

    def test_momentum_profile_records_shadow_breakout_candidate(self) -> None:
        request = momentum_request(datetime(2026, 7, 31, 10, 20, tzinfo=timezone.utc))

        response = evaluate_decision(request, settings(), "momentum_atr_breakout")

        self.assertEqual(response.action, DecisionAction.HOLD)
        self.assertEqual(response.reason, "momentum_atr_shadow_signal")
        self.assertTrue(response.metadata["candidate"])
        self.assertEqual(response.metadata["strategy_profile"], "momentum_atr_breakout")
        self.assertEqual(response.metadata["suggested_action"], "buy")
        self.assertIn("ema50", response.metadata)
        self.assertIn("breakout_level", response.metadata)

    def test_rsi_bollinger_profile_records_independent_shadow_candidate(self) -> None:
        request = mean_reversion_request(datetime(2026, 7, 31, 10, 20, tzinfo=timezone.utc))

        response = evaluate_decision(request, settings(), "rsi_bollinger_reversion")

        self.assertEqual(response.action, DecisionAction.HOLD)
        self.assertEqual(response.reason, "rsi_bollinger_shadow_signal")
        self.assertTrue(response.metadata["candidate"])
        self.assertEqual(response.metadata["strategy_profile"], "rsi_bollinger_reversion")
        self.assertEqual(response.metadata["suggested_action"], "buy")
        self.assertIn("rsi14", response.metadata)
        self.assertIn("bollinger_lower", response.metadata)

    def test_three_profiles_keep_independent_bot_scoped_state(self) -> None:
        candle_time = datetime(2026, 7, 31, 10, 20, tzinfo=timezone.utc)
        cases = [
            (bullish_request(candle_time), "fimath_ema20_flow"),
            (momentum_request(candle_time), "momentum_atr_breakout"),
            (mean_reversion_request(candle_time), "rsi_bollinger_reversion"),
        ]

        responses = [evaluate_decision(request, settings(), profile) for request, profile in cases]

        self.assertEqual({request.bot_id for request, _ in cases}, {"bot-1", "bot-2", "bot-3"})
        self.assertEqual(
            {response.metadata["strategy_profile"] for response in responses},
            {"fimath_ema20_flow", "momentum_atr_breakout", "rsi_bollinger_reversion"},
        )
        self.assertTrue(all(response.action == DecisionAction.HOLD for response in responses))

    def test_unknown_profile_fails_closed(self) -> None:
        response = evaluate_decision(
            bullish_request(datetime(2026, 7, 31, 10, 20, tzinfo=timezone.utc)),
            settings(),
            "unknown",
        )

        self.assertEqual(response.action, DecisionAction.HOLD)
        self.assertEqual(response.reason, "unsupported_strategy_profile")


if __name__ == "__main__":
    unittest.main()
