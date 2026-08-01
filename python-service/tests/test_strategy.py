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


def macd_trend_request(timestamp: datetime) -> DecisionRequest:
    closes = [100 + index * 0.03 for index in range(57)]
    closes.extend([closes[-1] - 0.05, closes[-1] - 0.10, closes[-1] + 0.40])
    candles = [
        CandleSnapshot(
            timestamp_utc=timestamp - timedelta(minutes=(len(closes) - index - 1) * 5),
            open=close - 0.03,
            high=close + 0.15,
            low=close - 0.15,
            close=close,
            volume=100 + index,
        )
        for index, close in enumerate(closes)
    ]
    return DecisionRequest(
        bot_id="bot-4",
        request_id=f"macd-trend-{timestamp.timestamp()}",
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


def stochastic_pullback_request(timestamp: datetime) -> DecisionRequest:
    closes = [100 + index * 0.03 for index in range(56)]
    closes.extend([closes[-1] - 0.2, closes[-1] - 0.4, closes[-1] - 0.6, closes[-1] + 0.2])
    candles = [
        CandleSnapshot(
            timestamp_utc=timestamp - timedelta(minutes=(len(closes) - index - 1) * 5),
            open=close - 0.05,
            high=close + 0.2,
            low=close - 0.2,
            close=close,
            volume=100 + index,
        )
        for index, close in enumerate(closes)
    ]
    return DecisionRequest(
        bot_id="bot-5",
        request_id=f"stochastic-pullback-{timestamp.timestamp()}",
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


def stochastic_sell_request(timestamp: datetime) -> DecisionRequest:
    request = stochastic_pullback_request(timestamp)
    request.bot_id = "bot-6"
    pivot = 200.0
    for candle in request.candles:
        old_open, old_high, old_low, old_close = candle.open, candle.high, candle.low, candle.close
        candle.open = pivot - old_open
        candle.high = pivot - old_low
        candle.low = pivot - old_high
        candle.close = pivot - old_close
    request.bid = request.candles[-1].close
    request.ask = request.bid + 0.1
    return request


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

    def test_macd_trend_profile_records_independent_shadow_candidate(self) -> None:
        request = macd_trend_request(datetime(2026, 7, 31, 10, 20, tzinfo=timezone.utc))

        response = evaluate_decision(request, settings(), "macd_trend_crossover")

        self.assertEqual(response.action, DecisionAction.HOLD)
        self.assertEqual(response.reason, "macd_trend_shadow_signal")
        self.assertTrue(response.metadata["candidate"])
        self.assertEqual(response.metadata["strategy_profile"], "macd_trend_crossover")
        self.assertEqual(response.metadata["suggested_action"], "buy")
        self.assertIn("macd_line", response.metadata)
        self.assertIn("macd_signal", response.metadata)
        self.assertGreater(response.metadata["macd_histogram"], 0)

    def test_stochastic_pullback_profile_records_independent_shadow_candidate(self) -> None:
        request = stochastic_pullback_request(datetime(2026, 7, 31, 10, 20, tzinfo=timezone.utc))

        response = evaluate_decision(request, settings(), "stochastic_trend_pullback")

        self.assertEqual(response.action, DecisionAction.HOLD)
        self.assertEqual(response.reason, "stochastic_pullback_shadow_signal")
        self.assertTrue(response.metadata["candidate"])
        self.assertEqual(response.metadata["strategy_profile"], "stochastic_trend_pullback")
        self.assertEqual(response.metadata["suggested_action"], "buy")
        self.assertGreater(response.metadata["stochastic_k"], response.metadata["stochastic_d"])
        self.assertIn("ema50", response.metadata)

    def test_stochastic_sell_experiment_blocks_buy_candidates(self) -> None:
        request = stochastic_pullback_request(datetime(2026, 7, 31, 10, 20, tzinfo=timezone.utc))
        request.bot_id = "bot-6"

        response = evaluate_decision(request, settings(), "stochastic_sell_session")

        self.assertEqual(response.action, DecisionAction.HOLD)
        self.assertEqual(response.reason, "experimental_side_or_session_block")
        self.assertFalse(response.metadata["candidate"])
        self.assertTrue(response.metadata["base_candidate"])
        self.assertEqual(response.metadata["experimental_block_reason"], "buy_side")

    def test_stochastic_sell_experiment_accepts_sell_before_18_utc(self) -> None:
        request = stochastic_sell_request(datetime(2026, 7, 31, 10, 20, tzinfo=timezone.utc))

        response = evaluate_decision(request, settings(), "stochastic_sell_session")

        self.assertEqual(response.action, DecisionAction.HOLD)
        self.assertEqual(response.reason, "stochastic_sell_session_shadow_signal")
        self.assertTrue(response.metadata["candidate"])
        self.assertEqual(response.metadata["suggested_action"], "sell")
        self.assertEqual(response.metadata["experiment"], "sell_only_entry_before_18utc")
        self.assertTrue(response.metadata["experimental_shadow_lock"])

    def test_stochastic_sell_experiment_stays_shadow_when_global_live_is_enabled(self) -> None:
        configured = settings()
        configured.enable_live_decisions = True
        configured.fimath_mode = "live"
        request = stochastic_sell_request(datetime(2026, 7, 31, 10, 20, tzinfo=timezone.utc))

        response = evaluate_decision(request, configured, "stochastic_sell_session")

        self.assertEqual(response.action, DecisionAction.HOLD)
        self.assertEqual(response.size, 0)
        self.assertEqual(response.reason, "stochastic_sell_session_shadow_signal")
        self.assertTrue(response.metadata["experimental_shadow_lock"])

    def test_stochastic_sell_experiment_blocks_entries_at_18_utc(self) -> None:
        request = stochastic_sell_request(datetime(2026, 7, 31, 18, 20, tzinfo=timezone.utc))

        response = evaluate_decision(request, settings(), "stochastic_sell_session")

        self.assertEqual(response.reason, "experimental_side_or_session_block")
        self.assertFalse(response.metadata["candidate"])
        self.assertEqual(response.metadata["experimental_block_reason"], "entry_at_or_after_18utc")

    def test_six_profiles_keep_independent_bot_scoped_state(self) -> None:
        candle_time = datetime(2026, 7, 31, 10, 20, tzinfo=timezone.utc)
        cases = [
            (bullish_request(candle_time), "fimath_ema20_flow"),
            (momentum_request(candle_time), "momentum_atr_breakout"),
            (mean_reversion_request(candle_time), "rsi_bollinger_reversion"),
            (macd_trend_request(candle_time), "macd_trend_crossover"),
            (stochastic_pullback_request(candle_time), "stochastic_trend_pullback"),
            (stochastic_sell_request(candle_time), "stochastic_sell_session"),
        ]

        responses = [evaluate_decision(request, settings(), profile) for request, profile in cases]

        self.assertEqual({request.bot_id for request, _ in cases}, {"bot-1", "bot-2", "bot-3", "bot-4", "bot-5", "bot-6"})
        self.assertEqual(
            {response.metadata["strategy_profile"] for response in responses},
            {"fimath_ema20_flow", "momentum_atr_breakout", "rsi_bollinger_reversion", "macd_trend_crossover", "stochastic_trend_pullback", "stochastic_sell_session"},
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
