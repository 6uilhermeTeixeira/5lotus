from __future__ import annotations

import argparse
import csv
import json
from collections import deque
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


PIP_SIZE = 0.01
LOT_SIZE = 0.10
USD_PER_PIP_AT_LOT = 0.10


@dataclass
class Position:
    side: str
    opened_msc: int
    entry: float
    stop: float
    target: float
    best: float
    signal_move_pips: float


@dataclass
class ClosedTrade:
    side: str
    opened_at_utc: str
    closed_at_utc: str
    entry_price: float
    exit_price: float
    exit_reason: str
    duration_seconds: float
    signal_move_pips: float
    pnl_pips: float
    net_pnl: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay the Bot 17 impulse strategy from daily Dukascopy ticks.")
    parser.add_argument("--ticks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold-pips", type=float, default=95.5)
    parser.add_argument("--signal-window-seconds", type=int, default=30)
    parser.add_argument("--max-spread-pips", type=float, default=50.0)
    parser.add_argument("--modeled-spread-pips", type=float)
    parser.add_argument("--mode", choices=("fixed", "managed"), default="managed")
    parser.add_argument("--max-hold-seconds", type=int, default=180)
    parser.add_argument("--effective-stop-pips", type=float, default=240.0)
    parser.add_argument("--commission-per-trade", type=float, default=0.0)
    parser.add_argument("--cooldown-seconds", type=int, default=0)
    parser.add_argument("--require-rearm", action="store_true")
    parser.add_argument("--rearm-ratio", type=float, default=0.5)
    parser.add_argument("--min-1s-tick-count", type=int, default=0)
    parser.add_argument("--min-1s-range-pips", type=float, default=0.0)
    parser.add_argument("--context-window-seconds", type=int, default=900)
    parser.add_argument("--min-context-move-pips", type=float, default=0.0)
    return parser.parse_args()


def iso_utc(time_msc: int) -> str:
    return datetime.fromtimestamp(time_msc / 1000, UTC).isoformat()


def close_position(position: Position, time_msc: int, exit_price: float, reason: str, commission: float) -> ClosedTrade:
    direction = 1 if position.side == "buy" else -1
    pnl_pips = direction * (exit_price - position.entry) / PIP_SIZE
    return ClosedTrade(
        side=position.side,
        opened_at_utc=iso_utc(position.opened_msc),
        closed_at_utc=iso_utc(time_msc),
        entry_price=round(position.entry, 5),
        exit_price=round(exit_price, 5),
        exit_reason=reason,
        duration_seconds=round((time_msc - position.opened_msc) / 1000, 3),
        signal_move_pips=round(position.signal_move_pips, 3),
        pnl_pips=round(pnl_pips, 3),
        net_pnl=round(pnl_pips * USD_PER_PIP_AT_LOT - commission, 2),
    )


def update_position(
    position: Position,
    time_msc: int,
    bid: float,
    ask: float,
    *,
    mode: str,
    max_hold_seconds: int,
    commission: float,
) -> ClosedTrade | None:
    if position.side == "buy":
        position.best = max(position.best, bid)
        if bid <= position.stop:
            return close_position(position, time_msc, bid, "stop", commission)
        if bid >= position.target:
            return close_position(position, time_msc, bid, "target", commission)
        favorable_pips = (position.best - position.entry) / PIP_SIZE
        if mode == "managed" and favorable_pips >= 120:
            position.stop = max(position.stop, position.best - 60 * PIP_SIZE)
        elif mode == "managed" and favorable_pips >= 40:
            position.stop = max(position.stop, position.entry)
        exit_price = bid
    else:
        position.best = min(position.best, ask)
        if ask >= position.stop:
            return close_position(position, time_msc, ask, "stop", commission)
        if ask <= position.target:
            return close_position(position, time_msc, ask, "target", commission)
        favorable_pips = (position.entry - position.best) / PIP_SIZE
        if mode == "managed" and favorable_pips >= 120:
            position.stop = min(position.stop, position.best + 60 * PIP_SIZE)
        elif mode == "managed" and favorable_pips >= 40:
            position.stop = min(position.stop, position.entry)
        exit_price = ask

    if (time_msc - position.opened_msc) >= max_hold_seconds * 1000:
        return close_position(position, time_msc, exit_price, "time", commission)
    return None


def tick_files(root: Path) -> list[Path]:
    return sorted(path for path in root.glob("xauusd-tick-*.csv") if path.with_suffix(path.suffix + ".complete").exists())


def replay(args: argparse.Namespace) -> tuple[list[ClosedTrade], dict[str, object]]:
    window: deque[tuple[int, float]] = deque()
    activity_window: deque[tuple[int, float]] = deque()
    context_window: deque[tuple[int, float]] = deque()
    trades: list[ClosedTrade] = []
    position: Position | None = None
    signal_minutes: set[int] = set()
    last_signal_msc: int | None = None
    armed = True
    first_msc: int | None = None
    last_msc: int | None = None
    rows = 0
    files = tick_files(args.ticks)

    for path in files:
        with path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                time_msc = int(row["timestamp"])
                source_ask = float(row["askPrice"])
                source_bid = float(row["bidPrice"])
                mid = (source_ask + source_bid) / 2
                if args.modeled_spread_pips is None:
                    ask, bid = source_ask, source_bid
                else:
                    half_spread = args.modeled_spread_pips * PIP_SIZE / 2
                    ask, bid = mid + half_spread, mid - half_spread
                rows += 1
                first_msc = time_msc if first_msc is None else first_msc
                last_msc = time_msc

                target_msc = time_msc - args.signal_window_seconds * 1000
                while len(window) >= 2 and window[1][0] <= target_msc:
                    window.popleft()
                while activity_window and activity_window[0][0] < time_msc - 1_000:
                    activity_window.popleft()
                context_target_msc = time_msc - args.context_window_seconds * 1000
                while len(context_window) >= 2 and context_window[1][0] <= context_target_msc:
                    context_window.popleft()

                if position is not None:
                    closed = update_position(
                        position,
                        time_msc,
                        bid,
                        ask,
                        mode=args.mode,
                        max_hold_seconds=args.max_hold_seconds,
                        commission=args.commission_per_trade,
                    )
                    if closed is not None:
                        trades.append(closed)
                        position = None

                timestamp = datetime.fromtimestamp(time_msc / 1000, UTC)
                minute_key = time_msc // 60_000
                spread_pips = (ask - bid) / PIP_SIZE
                move_pips = (mid - window[0][1]) / PIP_SIZE if window and window[0][0] <= target_msc else 0.0
                recent_mids = [value for _, value in activity_window]
                recent_mids.append(mid)
                one_second_count = len(recent_mids)
                one_second_range_pips = (
                    (max(recent_mids) - min(recent_mids)) / PIP_SIZE if recent_mids else 0.0
                )
                direction = 1 if move_pips > 0 else -1
                context_move_pips = (
                    direction * (mid - context_window[0][1]) / PIP_SIZE
                    if context_window and context_window[0][0] <= context_target_msc
                    else 0.0
                )
                if args.require_rearm and abs(move_pips) < args.threshold_pips * args.rearm_ratio:
                    armed = True
                if (
                    position is None
                    and window
                    and window[0][0] <= target_msc
                    and timestamp.hour < 17
                    and spread_pips <= args.max_spread_pips
                    and minute_key not in signal_minutes
                    and (last_signal_msc is None or time_msc - last_signal_msc >= args.cooldown_seconds * 1000)
                    and (armed or not args.require_rearm)
                    and one_second_count >= args.min_1s_tick_count
                    and one_second_range_pips >= args.min_1s_range_pips
                    and context_move_pips >= args.min_context_move_pips
                ):
                    if abs(move_pips) >= args.threshold_pips:
                        side = "buy" if move_pips > 0 else "sell"
                        entry = ask if side == "buy" else bid
                        direction = 1 if side == "buy" else -1
                        position = Position(
                            side=side,
                            opened_msc=time_msc,
                            entry=entry,
                            stop=entry - direction * args.effective_stop_pips * PIP_SIZE,
                            target=entry + direction * 1000 * PIP_SIZE,
                            best=bid if side == "buy" else ask,
                            signal_move_pips=move_pips,
                        )
                        signal_minutes.add(minute_key)
                        last_signal_msc = time_msc
                        armed = False
                window.append((time_msc, mid))
                activity_window.append((time_msc, mid))
                context_window.append((time_msc, mid))

    if position is not None and last_msc is not None:
        trades.append(close_position(position, last_msc, position.best, "end_of_data", args.commission_per_trade))

    wins = sum(trade.net_pnl > 0 for trade in trades)
    losses = sum(trade.net_pnl < 0 for trade in trades)
    gross_profit = sum(max(0.0, trade.net_pnl) for trade in trades)
    gross_loss = -sum(min(0.0, trade.net_pnl) for trade in trades)
    equity = peak = drawdown = 0.0
    for trade in trades:
        equity += trade.net_pnl
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    summary = {
        "strategy_profile": "happy_gold_tick_impulse_shadow",
        "source": "Dukascopy XAUUSD ticks",
        "mode": args.mode,
        "files": len(files),
        "ticks": rows,
        "period_start_utc": iso_utc(first_msc) if first_msc else None,
        "period_end_utc": iso_utc(last_msc) if last_msc else None,
        "threshold_pips": args.threshold_pips,
        "signal_window_seconds": args.signal_window_seconds,
        "max_spread_pips": args.max_spread_pips,
        "modeled_spread_pips": args.modeled_spread_pips,
        "max_hold_seconds": args.max_hold_seconds,
        "effective_stop_pips": args.effective_stop_pips,
        "cooldown_seconds": args.cooldown_seconds,
        "require_rearm": args.require_rearm,
        "rearm_ratio": args.rearm_ratio,
        "min_1s_tick_count": args.min_1s_tick_count,
        "min_1s_range_pips": args.min_1s_range_pips,
        "context_window_seconds": args.context_window_seconds,
        "min_context_move_pips": args.min_context_move_pips,
        "fixed_lot": LOT_SIZE,
        "trades_count": len(trades),
        "wins": wins,
        "losses": losses,
        "breakevens": len(trades) - wins - losses,
        "win_rate_pct": round(100 * wins / len(trades), 2) if trades else 0.0,
        "net_pnl": round(sum(trade.net_pnl for trade in trades), 2),
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else None,
        "max_drawdown_amount": round(drawdown, 2),
        "assumptions": [
            f"Signals use a rolling {args.signal_window_seconds}-second mid-price move and are deduplicated by UTC minute.",
            "Buy fills use Ask and sell fills use Bid; exits use the executable opposite quote.",
            f"The effective replay stop is {args.effective_stop_pips:g} pips, target is 1000 pips, and position size is fixed at 0.10 lot.",
            "Managed mode moves to break-even after 40 favorable pips and trails by 60 after 120 pips.",
            "Dukascopy is a proxy for the undisclosed broker used by the original forward test.",
        ],
    }
    return trades, summary


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    trades, summary = replay(args)
    gate = f"_cooldown{args.cooldown_seconds}_rearm{args.rearm_ratio:g}" if args.require_rearm else ""
    spread = f"_spread{args.modeled_spread_pips:g}" if args.modeled_spread_pips is not None else ""
    signal = f"_{args.signal_window_seconds}s_threshold{args.threshold_pips:g}"
    stop = f"_stop{args.effective_stop_pips:g}" if args.effective_stop_pips != 240 else ""
    activity = f"_ticks{args.min_1s_tick_count}_range{args.min_1s_range_pips:g}" if args.min_1s_tick_count or args.min_1s_range_pips else ""
    context = f"_context{args.context_window_seconds}s_{args.min_context_move_pips:g}" if args.min_context_move_pips else ""
    stem = f"happy_gold_tick_impulse_2025_{args.mode}{signal}{spread}{stop}{gate}{activity}{context}"
    with (args.output / f"{stem}.trades.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(trades[0]).keys()) if trades else list(ClosedTrade.__annotations__))
        writer.writeheader()
        writer.writerows(asdict(trade) for trade in trades)
    (args.output / f"{stem}.summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
