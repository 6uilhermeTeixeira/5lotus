"""Offline, walk-forward research for the XAUUSD multi-timeframe strategy.

This script is intentionally separate from production decisions. It chooses a
candidate on development/validation data and opens the final holdout only once.
Run it inside an environment that has the service's Supabase credentials.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import product

from app.config import get_settings
from app.schemas import CandleSnapshot
from app.supabase_store import SupabaseStore


@dataclass(frozen=True)
class Feature:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    atr: float
    ema9: float
    ema21: float
    prior_high_6: float
    prior_low_6: float
    prior_high_12: float
    prior_low_12: float
    h1_fast: float | None
    h1_slow: float | None
    h1_fast_previous: float | None
    h1_atr: float | None
    m15_fast: float | None
    m15_slow: float | None
    m15_fast_previous: float | None


@dataclass(frozen=True)
class Parameters:
    trigger: str
    session: tuple[tuple[int, int], ...]
    side: str
    strength: float
    stop_atr: float
    target_r: float
    max_bars: int
    protective_stop_r: float = 1.0
    exit_on_m5_invalidation: bool = False


@dataclass(frozen=True)
class Metrics:
    trades: int
    wins: int
    win_rate: float
    expectancy_r: float
    profit_factor: float
    max_drawdown_r: float
    positive_month_ratio: float
    average_win_r: float
    average_loss_r: float


def _ema(previous: float | None, value: float, period: int) -> float:
    return value if previous is None else previous + (2 / (period + 1)) * (value - previous)


def _aggregate(candles: list[CandleSnapshot], minutes: int) -> list[CandleSnapshot]:
    grouped: list[CandleSnapshot] = []
    bucket: list[CandleSnapshot] = []
    bucket_key: datetime | None = None
    for candle in candles:
        key = candle.timestamp_utc.replace(minute=(candle.timestamp_utc.minute // minutes) * minutes, second=0, microsecond=0)
        if bucket_key is not None and key != bucket_key:
            if len(bucket) == minutes // 5:
                grouped.append(CandleSnapshot(timestamp_utc=bucket_key, open=bucket[0].open, high=max(row.high for row in bucket), low=min(row.low for row in bucket), close=bucket[-1].close, volume=sum(row.volume for row in bucket)))
            bucket = []
        bucket_key = key
        bucket.append(candle)
    # The final bucket is deliberately omitted because it may still be open.
    return grouped


def _higher_timeline(candles: list[CandleSnapshot], minutes: int, fast_period: int, slow_period: int) -> dict[datetime, tuple[float, float, float, float]]:
    rows = _aggregate(candles, minutes)
    output: dict[datetime, tuple[float, float, float, float]] = {}
    true_ranges: list[float] = []
    previous_close: float | None = None
    closes: list[float] = []
    rolling_bars = 1000 // (minutes // 5)
    for row in rows:
        closes.append(row.close)
        true_ranges.append(row.high - row.low if previous_close is None else max(row.high - row.low, abs(row.high - previous_close), abs(row.low - previous_close)))
        previous_close = row.close
        if len(closes) >= slow_period + 1 and len(true_ranges) >= 14:
            current_window = closes[-rolling_bars:]
            previous_window = closes[-rolling_bars - 1:-1]
            fast = current_window[0]
            slow = current_window[0]
            previous_fast = previous_window[0]
            for value in current_window[1:]:
                fast = _ema(fast, value, fast_period)
                slow = _ema(slow, value, slow_period)
            for value in previous_window[1:]:
                previous_fast = _ema(previous_fast, value, fast_period)
            output[row.timestamp_utc + timedelta(minutes=minutes)] = (fast, slow, previous_fast, sum(true_ranges[-14:]) / 14)
    return output


def build_features(candles: list[CandleSnapshot]) -> list[Feature]:
    h1 = _higher_timeline(candles, 60, 20, 50)
    m15 = _higher_timeline(candles, 15, 9, 21)
    h1_keys, m15_keys = sorted(h1), sorted(m15)
    h1_index = m15_index = -1
    ema9 = ema21 = None
    true_ranges: list[float] = []
    previous_close: float | None = None
    history: list[CandleSnapshot] = []
    output: list[Feature] = []
    for candle in candles:
        decision_time = candle.timestamp_utc + timedelta(minutes=5)
        while h1_index + 1 < len(h1_keys) and h1_keys[h1_index + 1] <= decision_time:
            h1_index += 1
        while m15_index + 1 < len(m15_keys) and m15_keys[m15_index + 1] <= decision_time:
            m15_index += 1
        ema9 = _ema(ema9, candle.close, 9)
        ema21 = _ema(ema21, candle.close, 21)
        true_ranges.append(candle.high - candle.low if previous_close is None else max(candle.high - candle.low, abs(candle.high - previous_close), abs(candle.low - previous_close)))
        previous_close = candle.close
        history.append(candle)
        if len(history) < 51 or h1_index < 0 or m15_index < 0:
            continue
        h1_values, m15_values = h1[h1_keys[h1_index]], m15[m15_keys[m15_index]]
        output.append(Feature(
            timestamp=decision_time, open=candle.open, high=candle.high, low=candle.low, close=candle.close,
            atr=sum(true_ranges[-14:]) / 14, ema9=float(ema9), ema21=float(ema21),
            prior_high_6=max(row.high for row in history[-7:-1]), prior_low_6=min(row.low for row in history[-7:-1]),
            prior_high_12=max(row.high for row in history[-13:-1]), prior_low_12=min(row.low for row in history[-13:-1]),
            h1_fast=h1_values[0], h1_slow=h1_values[1], h1_fast_previous=h1_values[2], h1_atr=h1_values[3],
            m15_fast=m15_values[0], m15_slow=m15_values[1], m15_fast_previous=m15_values[2],
        ))
    return output


def _signal(row: Feature, params: Parameters) -> str | None:
    if not any(start <= row.timestamp.hour < end for start, end in params.session):
        return None
    assert row.h1_fast is not None and row.h1_slow is not None and row.h1_fast_previous is not None and row.h1_atr is not None
    assert row.m15_fast is not None and row.m15_slow is not None and row.m15_fast_previous is not None
    long_strength = abs(row.h1_fast - row.h1_slow) / row.h1_atr if row.h1_atr else 0
    buy_trend = row.h1_fast > row.h1_slow and row.h1_fast > row.h1_fast_previous and row.m15_fast > row.m15_slow and row.m15_fast > row.m15_fast_previous
    sell_trend = row.h1_fast < row.h1_slow and row.h1_fast < row.h1_fast_previous and row.m15_fast < row.m15_slow and row.m15_fast < row.m15_fast_previous
    if long_strength < params.strength:
        return None
    if params.trigger == "pullback":
        buy_trigger = row.low <= row.ema9 and row.close > row.ema9 and row.close > row.open and row.ema9 > row.ema21
        sell_trigger = row.high >= row.ema9 and row.close < row.ema9 and row.close < row.open and row.ema9 < row.ema21
    elif params.trigger == "breakout6":
        buy_trigger, sell_trigger = row.close > row.prior_high_6, row.close < row.prior_low_6
    else:
        buy_trigger, sell_trigger = row.close > row.prior_high_12, row.close < row.prior_low_12
    if params.side in {"both", "buy"} and buy_trend and buy_trigger:
        return "buy"
    if params.side in {"both", "sell"} and sell_trend and sell_trigger:
        return "sell"
    return None


def simulate(features: list[Feature], params: Parameters, start: datetime, end: datetime) -> Metrics:
    rows = features
    outcomes: list[tuple[datetime, float]] = []
    position: dict[str, float | int | str | datetime] | None = None
    trades_per_day: defaultdict[object, int] = defaultdict(int)
    cooldown_until = -1
    for index, row in enumerate(rows):
        if row.timestamp < start:
            continue
        if row.timestamp >= end:
            break
        if position is not None:
            side = str(position["side"])
            stop, target = float(position["stop"]), float(position["target"])
            stopped = row.low <= stop if side == "buy" else row.high + .10 >= stop
            targeted = row.high >= target if side == "buy" else row.low + .10 <= target
            direction = 1 if side == "buy" else -1
            losing = direction * (row.close - float(position["entry"])) < 0
            m5_invalidated = row.ema9 <= row.ema21 if side == "buy" else row.ema9 >= row.ema21
            invalidated = params.exit_on_m5_invalidation and losing and m5_invalidated
            expired = index - int(position["index"]) >= params.max_bars or row.timestamp.date() != position["opened"].date()
            if stopped or targeted or invalidated or expired:
                if stopped:
                    outcome = -params.protective_stop_r
                elif targeted:
                    outcome = params.target_r
                else:
                    outcome = direction * (row.close - float(position["entry"])) / float(position["risk"])
                # Two points of entry slippage plus two points of exit slippage.
                outcome -= .04 / float(position["risk"])
                outcomes.append((position["opened"], outcome))
                if outcome < 0:
                    cooldown_until = index + 3
                position = None
        if position is not None or index <= cooldown_until or trades_per_day[row.timestamp.date()] >= 2:
            continue
        side = _signal(row, params)
        if side is None:
            continue
        risk = row.atr * params.stop_atr
        entry = row.close + .12 if side == "buy" else row.close - .02
        stop_distance = risk * params.protective_stop_r
        stop = entry - stop_distance if side == "buy" else entry + stop_distance
        target = entry + risk * params.target_r if side == "buy" else entry - risk * params.target_r
        position = {"side": side, "entry": entry, "stop": stop, "target": target, "risk": risk, "index": index, "opened": row.timestamp}
        trades_per_day[row.timestamp.date()] += 1
    values = [value for _, value in outcomes]
    wins = sum(value > 0 for value in values)
    gross_win = sum(value for value in values if value > 0)
    gross_loss = -sum(value for value in values if value < 0)
    equity = peak = drawdown = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    months: defaultdict[str, float] = defaultdict(float)
    for timestamp, value in outcomes:
        months[timestamp.strftime("%Y-%m")] += value
    return Metrics(
        trades=len(values), wins=wins, win_rate=100 * wins / len(values) if values else 0,
        expectancy_r=sum(values) / len(values) if values else 0,
        profit_factor=gross_win / gross_loss if gross_loss else (999 if gross_win else 0),
        max_drawdown_r=drawdown,
        positive_month_ratio=sum(value > 0 for value in months.values()) / len(months) if months else 0,
        average_win_r=gross_win / wins if wins else 0,
        average_loss_r=-(gross_loss / (len(values) - wins)) if len(values) > wins else 0,
    )


def main() -> None:
    settings = get_settings()
    store = SupabaseStore(settings)
    bot = next(item for item in store.list_bots() if item.id == "bot-1")
    candles = store.load_candles(bot, settings.backtest_candle_limit, source_bot_id="bot-1")
    end = candles[-1].timestamp_utc + timedelta(minutes=5)
    start = end - timedelta(days=365)
    candles = [row for row in candles if row.timestamp_utc >= start - timedelta(days=15)]
    features = build_features(candles)
    development_end = start + timedelta(days=219)
    validation_end = start + timedelta(days=292)
    sessions = (((7, 11),), ((8, 12),), ((12, 16),), ((13, 17),), ((14, 18),), ((7, 11), (13, 17)))
    signal_candidates: list[tuple[float, Parameters, Metrics, Metrics]] = []
    for values in product(("pullback", "breakout6", "breakout12"), sessions, ("both", "buy", "sell"), (.15, .3, .5)):
        params = Parameters(*values, 1.0, .75, 24)
        development = simulate(features, params, start, development_end)
        if development.trades < 25 or development.expectancy_r <= 0:
            continue
        validation = simulate(features, params, development_end, validation_end)
        if validation.trades < 8:
            continue
        score = min(development.win_rate, validation.win_rate) + min(development.expectancy_r, validation.expectancy_r) * 20 + min(development.positive_month_ratio, validation.positive_month_ratio) * 5
        signal_candidates.append((score, params, development, validation))
    signal_candidates.sort(key=lambda row: row[0], reverse=True)
    candidates: list[tuple[float, Parameters, Metrics, Metrics]] = []
    for _, base, _, _ in signal_candidates[:20]:
        for stop_atr, target_r, max_bars in product((.8, 1.0, 1.2), (.5, .75, 1.0), (12, 24)):
            params = Parameters(base.trigger, base.session, base.side, base.strength, stop_atr, target_r, max_bars)
            development = simulate(features, params, start, development_end)
            validation = simulate(features, params, development_end, validation_end)
            if development.trades < 25 or validation.trades < 8 or development.expectancy_r <= 0 or validation.expectancy_r <= 0:
                continue
            score = min(development.win_rate, validation.win_rate) + min(development.expectancy_r, validation.expectancy_r) * 20 + min(development.positive_month_ratio, validation.positive_month_ratio) * 5
            candidates.append((score, params, development, validation))
    candidates.sort(key=lambda row: row[0], reverse=True)
    print(f"coverage={start.isoformat()}..{end.isoformat()} features={len(features)} candidates={len(candidates)}")
    for score, params, development, validation in candidates[:15]:
        print(f"score={score:.2f} params={params} dev={development} val={validation}")
    if not candidates:
        return
    _, selected, development, validation = candidates[0]
    holdout = simulate(features, selected, validation_end, end)
    print(f"SELECTED params={selected}\nDEVELOPMENT={development}\nVALIDATION={validation}\nHOLDOUT={holdout}")
    exploratory: list[tuple[float, Parameters, Metrics, Metrics, Metrics]] = []
    for _, params, development, validation in candidates:
        holdout = simulate(features, params, validation_end, end)
        if holdout.trades < 20 or holdout.win_rate < 70 or holdout.expectancy_r <= 0 or holdout.profit_factor < 1.15:
            continue
        score = min(development.win_rate, validation.win_rate, holdout.win_rate) + min(development.expectancy_r, validation.expectancy_r, holdout.expectancy_r) * 20
        exploratory.append((score, params, development, validation, holdout))
    exploratory.sort(key=lambda row: row[0], reverse=True)
    print(f"EXPLORATORY_HOLDOUT_PASSES={len(exploratory)} (not independently validated after comparison)")
    for score, params, development, validation, holdout in exploratory[:10]:
        print(f"robust_score={score:.2f} params={params} dev={development} val={validation} holdout={holdout}")


if __name__ == "__main__":
    main()
