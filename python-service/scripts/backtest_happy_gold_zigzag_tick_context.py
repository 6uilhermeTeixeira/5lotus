from __future__ import annotations

import argparse
import csv
import json
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path


PIP_SIZE = 0.01
LOT_SIZE = 0.10
USD_PER_PIP = 0.10


@dataclass
class Bar:
    bucket_msc: int
    open: float
    high: float
    low: float
    close: float
    count: int = 1

    def update(self, price: float) -> None:
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.count += 1


@dataclass
class Position:
    side: str
    opened_msc: int
    entry: float
    stop: float
    target: float
    best: float
    context_move_pips: float
    pivot: float


@dataclass
class ClosedTrade:
    side: str
    opened_at_utc: str
    closed_at_utc: str
    entry_price: float
    exit_price: float
    exit_reason: str
    duration_seconds: float
    context_move_pips: float
    pivot: float
    pnl_pips: float
    net_pnl: float


@dataclass
class Scenario:
    name: str
    stop_pips: float
    max_hold_seconds: int
    managed: bool
    position: Position | None = None
    trades: list[ClosedTrade] = field(default_factory=list)
    last_signal_msc: int | None = None
    signal_buckets: set[int] = field(default_factory=set)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Annual causal tick replay for ZigZag + 15-minute context.")
    parser.add_argument("--ticks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--context-threshold-pips", type=float, default=800)
    parser.add_argument("--modeled-spread-pips", type=float, default=10)
    parser.add_argument("--cooldown-seconds", type=int, default=5400)
    parser.add_argument("--session-start-hour", type=int, default=3)
    parser.add_argument("--session-end-hour", type=int, default=19)
    parser.add_argument("--structural-selector", action="store_true")
    parser.add_argument("--structural-ema-gap-pips", type=float, default=900)
    parser.add_argument("--structural-max-extension-pips", type=float, default=50)
    parser.add_argument("--output-prefix", default="happy_gold_zigzag_tick_context_2025")
    return parser.parse_args()


def files(root: Path) -> list[Path]:
    return sorted(
        path for path in root.glob("xauusd-tick-*.csv")
        if path.with_suffix(path.suffix + ".complete").exists()
    )


def close_position(position: Position, time_msc: int, price: float, reason: str) -> ClosedTrade:
    direction = 1 if position.side == "buy" else -1
    pnl_pips = direction * (price - position.entry) / PIP_SIZE
    return ClosedTrade(
        side=position.side,
        opened_at_utc=datetime.fromtimestamp(position.opened_msc / 1000, UTC).isoformat(),
        closed_at_utc=datetime.fromtimestamp(time_msc / 1000, UTC).isoformat(),
        entry_price=round(position.entry, 5), exit_price=round(price, 5),
        exit_reason=reason,
        duration_seconds=round((time_msc - position.opened_msc) / 1000, 3),
        context_move_pips=round(position.context_move_pips, 3), pivot=round(position.pivot, 5),
        pnl_pips=round(pnl_pips, 3), net_pnl=round(pnl_pips * USD_PER_PIP, 2),
    )


def update_scenario(scenario: Scenario, time_msc: int, bid: float, ask: float) -> None:
    position = scenario.position
    if position is None:
        return
    if position.side == "buy":
        position.best = max(position.best, bid)
        favorable = (position.best - position.entry) / PIP_SIZE
        if scenario.managed and favorable >= 120:
            position.stop = max(position.stop, position.best - 60 * PIP_SIZE)
        elif scenario.managed and favorable >= 40:
            position.stop = max(position.stop, position.entry)
        if bid <= position.stop:
            trade = close_position(position, time_msc, bid, "stop")
        elif bid >= position.target:
            trade = close_position(position, time_msc, bid, "target")
        elif time_msc - position.opened_msc >= scenario.max_hold_seconds * 1000:
            trade = close_position(position, time_msc, bid, "time")
        else:
            return
    else:
        position.best = min(position.best, ask)
        favorable = (position.entry - position.best) / PIP_SIZE
        if scenario.managed and favorable >= 120:
            position.stop = min(position.stop, position.best + 60 * PIP_SIZE)
        elif scenario.managed and favorable >= 40:
            position.stop = min(position.stop, position.entry)
        if ask >= position.stop:
            trade = close_position(position, time_msc, ask, "stop")
        elif ask <= position.target:
            trade = close_position(position, time_msc, ask, "target")
        elif time_msc - position.opened_msc >= scenario.max_hold_seconds * 1000:
            trade = close_position(position, time_msc, ask, "time")
        else:
            return
    scenario.trades.append(trade)
    scenario.position = None


def summary(scenario: Scenario, args: argparse.Namespace, tick_count: int) -> dict[str, object]:
    wins = [trade for trade in scenario.trades if trade.net_pnl > 0]
    losses = [trade for trade in scenario.trades if trade.net_pnl < 0]
    gross_profit = sum(trade.net_pnl for trade in wins)
    gross_loss = -sum(trade.net_pnl for trade in losses)
    equity = peak = drawdown = 0.0
    for trade in scenario.trades:
        equity += trade.net_pnl
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return {
        "strategy_profile": "happy_gold_zigzag_tick_context_shadow",
        "scenario": scenario.name, "ticks": tick_count,
        "context_threshold_pips": args.context_threshold_pips,
        "modeled_spread_pips": args.modeled_spread_pips,
        "cooldown_seconds": args.cooldown_seconds,
        "stop_pips": scenario.stop_pips,
        "max_hold_seconds": scenario.max_hold_seconds,
        "managed": scenario.managed,
        "structural_selector": args.structural_selector,
        "structural_ema_gap_pips": args.structural_ema_gap_pips,
        "structural_max_extension_pips": args.structural_max_extension_pips,
        "trades_count": len(scenario.trades), "wins": len(wins), "losses": len(losses),
        "breakevens": len(scenario.trades) - len(wins) - len(losses),
        "win_rate_pct": round(100 * len(wins) / len(scenario.trades), 2) if scenario.trades else 0,
        "net_pnl": round(sum(trade.net_pnl for trade in scenario.trades), 2),
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else None,
        "max_drawdown_amount": round(drawdown, 2),
    }


def main() -> None:
    args = parse_args()
    scenarios = [
        Scenario(f"fixed_stop{stop}_hold{hold}", stop, hold, False)
        for stop in (30, 60, 240) for hold in (30, 60)
    ] + [
        Scenario(f"managed_stop{stop}_hold{hold}", stop, hold, True)
        for stop in (60, 240) for hold in (30, 60)
    ]
    context: deque[tuple[int, float]] = deque()
    completed_m5: deque[Bar] = deque(maxlen=1000)
    completed_m30: deque[Bar] = deque(maxlen=1000)
    m5: Bar | None = None
    m30: Bar | None = None
    pivot_high: float | None = None
    pivot_low: float | None = None
    tick_count = 0
    last_time_msc = 0

    for path in files(args.ticks):
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                time_msc = int(row["timestamp"])
                source_ask = float(row["askPrice"])
                source_bid = float(row["bidPrice"])
                mid = (source_ask + source_bid) / 2
                half_spread = args.modeled_spread_pips * PIP_SIZE / 2
                ask, bid = mid + half_spread, mid - half_spread
                tick_count += 1
                last_time_msc = time_msc

                m5_bucket = time_msc // 300_000 * 300_000
                if m5 is None or m5.bucket_msc != m5_bucket:
                    if m5 is not None:
                        completed_m5.append(m5)
                        m30_bucket = m5.bucket_msc // 1_800_000 * 1_800_000
                        if m30 is None or m30.bucket_msc != m30_bucket:
                            if m30 is not None:
                                completed_m30.append(m30)
                                if len(completed_m30) >= 5:
                                    candidate = completed_m30[-3]
                                    window = list(completed_m30)[-5:]
                                    if candidate.high == max(bar.high for bar in window):
                                        pivot_high = candidate.high
                                    if candidate.low == min(bar.low for bar in window):
                                        pivot_low = candidate.low
                            m30 = Bar(m30_bucket, m5.open, m5.high, m5.low, m5.close, m5.count)
                        else:
                            m30.high = max(m30.high, m5.high)
                            m30.low = min(m30.low, m5.low)
                            m30.close = m5.close
                            m30.count += m5.count
                    m5 = Bar(m5_bucket, mid, mid, mid, mid)
                else:
                    m5.update(mid)

                while len(context) >= 2 and context[1][0] <= time_msc - 900_000:
                    context.popleft()
                for scenario in scenarios:
                    update_scenario(scenario, time_msc, bid, ask)

                timestamp = datetime.fromtimestamp(time_msc / 1000, UTC)
                previous_close = completed_m5[-1].close if completed_m5 else None
                buy_breakout = previous_close is not None and pivot_high is not None and previous_close <= pivot_high < ask
                sell_breakout = previous_close is not None and pivot_low is not None and previous_close >= pivot_low > bid
                ready = context and context[0][0] <= time_msc - 900_000
                if ready and (buy_breakout or sell_breakout) and args.session_start_hour <= timestamp.hour < args.session_end_hour:
                    if buy_breakout and sell_breakout:
                        buy_breakout = ask - float(pivot_high) >= float(pivot_low) - bid
                        sell_breakout = not buy_breakout
                    side = "buy" if buy_breakout else "sell"
                    direction = 1 if side == "buy" else -1
                    move_pips = direction * (mid - context[0][1]) / PIP_SIZE
                    pivot = float(pivot_high if side == "buy" else pivot_low)
                    closes = [bar.close for bar in completed_m5]
                    ema20 = None
                    if len(closes) >= 20:
                        alpha = 2 / 21
                        ema20 = closes[-20]
                        for close in closes[-19:]:
                            ema20 = alpha * close + (1 - alpha) * ema20
                    ema_gap_pips = (
                        direction * (closes[-1] - ema20) / PIP_SIZE
                        if ema20 is not None else float("-inf")
                    )
                    executable_entry = ask if side == "buy" else bid
                    extension_pips = direction * (executable_entry - pivot) / PIP_SIZE
                    structural_pass = (
                        not args.structural_selector
                        or (
                            timestamp.weekday() != 4
                            and ema_gap_pips >= args.structural_ema_gap_pips
                            and extension_pips <= args.structural_max_extension_pips
                        )
                    )
                    if move_pips >= args.context_threshold_pips and structural_pass:
                        for scenario in scenarios:
                            if (
                                scenario.position is None
                                and m5_bucket not in scenario.signal_buckets
                                and (scenario.last_signal_msc is None or time_msc - scenario.last_signal_msc >= args.cooldown_seconds * 1000)
                            ):
                                entry = ask if side == "buy" else bid
                                scenario.position = Position(
                                    side=side, opened_msc=time_msc, entry=entry,
                                    stop=entry - direction * scenario.stop_pips * PIP_SIZE,
                                    target=entry + direction * 1000 * PIP_SIZE,
                                    best=bid if side == "buy" else ask,
                                    context_move_pips=move_pips, pivot=pivot,
                                )
                                scenario.signal_buckets.add(m5_bucket)
                                scenario.last_signal_msc = time_msc
                context.append((time_msc, mid))

    for scenario in scenarios:
        if scenario.position is not None:
            price = scenario.position.best
            scenario.trades.append(close_position(scenario.position, last_time_msc, price, "end_of_data"))
            scenario.position = None

    args.output.mkdir(parents=True, exist_ok=True)
    summaries = [summary(scenario, args, tick_count) for scenario in scenarios]
    (args.output / f"{args.output_prefix}.summary.json").write_text(
        json.dumps({"scenarios": summaries}, indent=2) + "\n", encoding="utf-8"
    )
    for scenario in scenarios:
        with (args.output / f"{args.output_prefix}_{scenario.name}.trades.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(ClosedTrade.__annotations__))
            writer.writeheader()
            writer.writerows(asdict(trade) for trade in scenario.trades)
    print(json.dumps({"scenarios": summaries}, indent=2))


if __name__ == "__main__":
    main()
