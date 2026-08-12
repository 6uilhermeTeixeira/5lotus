"""Exhaustive tick replay for the Happy Gold multiwindow score shadow strategy."""

from __future__ import annotations

import argparse
import bisect
import csv
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path


PIP_SIZE = 0.01
USD_PER_PIP = 0.10
WINDOWS = (5, 10, 30, 60, 300, 900)
THRESHOLDS = {5: 15.0, 10: 32.5, 30: 76.0, 60: 79.0, 300: 324.5, 900: 372.35}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticks", type=Path, required=True)
    parser.add_argument("--trades-output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--poll-seconds", type=int, default=5)
    parser.add_argument("--modeled-spread-pips", type=float, default=10)
    parser.add_argument("--cooldown-seconds", type=int, default=0)
    return parser.parse_args()


def completed_files(root: Path) -> list[Path]:
    return sorted(marker.with_suffix("") for marker in root.glob("xauusd-tick-*.csv.complete"))


def load_ticks(path: Path) -> tuple[list[int], list[float]]:
    timestamps: list[int] = []
    mids: list[float] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            timestamps.append(int(row["timestamp"]))
            mids.append((float(row["askPrice"]) + float(row["bidPrice"])) / 2)
    return timestamps, mids


def signal_at(timestamps: list[int], mids: list[float], index: int) -> tuple[int, int, dict[int, float]] | None:
    now = timestamps[index]
    moves: dict[int, float] = {}
    for seconds in WINDOWS:
        reference = bisect.bisect_left(timestamps, now - seconds * 1000, 0, index + 1)
        if reference >= index or timestamps[reference] > now - seconds * 1000 + 2000:
            return None
        moves[seconds] = (mids[index] - mids[reference]) / PIP_SIZE
    direction = 1 if moves[60] > 0 else -1
    passed = {seconds: direction * moves[seconds] >= THRESHOLDS[seconds] for seconds in WINDOWS}
    score = sum(passed.values())
    if all(passed[seconds] for seconds in (60, 300, 900)) and score >= 4:
        return direction, score, moves
    return None


def simulate_exit(
    timestamps: list[int], mids: list[float], index: int, direction: int, spread_pips: float
) -> dict[str, object]:
    half_spread = spread_pips * PIP_SIZE / 2
    entry = mids[index] + direction * half_spread
    stop = entry - direction * 60 * PIP_SIZE
    best = entry
    exit_price = mids[index] - direction * half_spread
    exit_index = index
    reason = "timeout"
    end_msc = timestamps[index] + 60_000
    for cursor in range(index, bisect.bisect_right(timestamps, end_msc, index)):
        executable = mids[cursor] - direction * half_spread
        best = max(best, executable) if direction > 0 else min(best, executable)
        favorable = direction * (best - entry) / PIP_SIZE
        if favorable >= 40:
            trailing = best - direction * 20 * PIP_SIZE
            stop = max(stop, trailing) if direction > 0 else min(stop, trailing)
            breakeven = entry + direction * PIP_SIZE
            stop = max(stop, breakeven) if direction > 0 else min(stop, breakeven)
        if (direction > 0 and executable <= stop) or (direction < 0 and executable >= stop):
            exit_price, exit_index, reason = executable, cursor, "stop"
            break
        exit_price, exit_index = executable, cursor
    pnl_pips = direction * (exit_price - entry) / PIP_SIZE
    return {
        "closed_at_utc": datetime.fromtimestamp(timestamps[exit_index] / 1000, UTC).isoformat(),
        "exit_price": round(exit_price, 6), "exit_reason": reason,
        "duration_seconds": round((timestamps[exit_index] - timestamps[index]) / 1000, 3),
        "pnl_pips": round(pnl_pips, 3), "net_pnl": round(pnl_pips * USD_PER_PIP, 2),
    }


def metrics(trades: list[dict[str, object]]) -> dict[str, object]:
    wins = [trade for trade in trades if float(trade["net_pnl"]) > 0]
    losses = [trade for trade in trades if float(trade["net_pnl"]) < 0]
    breakevens = len(trades) - len(wins) - len(losses)
    gross_profit = sum(float(trade["net_pnl"]) for trade in wins)
    gross_loss = -sum(float(trade["net_pnl"]) for trade in losses)
    equity = peak = drawdown = 0.0
    for trade in trades:
        equity += float(trade["net_pnl"])
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return {
        "trades_count": len(trades), "wins": len(wins), "losses": len(losses), "breakevens": breakevens,
        "win_rate_pct": round(100 * len(wins) / len(trades), 3) if trades else 0,
        "net_pnl": round(equity, 2), "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else 0,
        "max_drawdown_amount": round(drawdown, 2),
    }


def main() -> None:
    args = parse_args()
    trades: list[dict[str, object]] = []
    ticks_scanned = candidates = 0
    for path in completed_files(args.ticks):
        if path.stat().st_size == 0:
            continue
        timestamps, mids = load_ticks(path)
        ticks_scanned += len(timestamps)
        if not timestamps:
            continue
        next_poll = timestamps[0] + 900_000
        armed = True
        next_allowed = 0
        index = bisect.bisect_left(timestamps, next_poll)
        while index < len(timestamps):
            signal = signal_at(timestamps, mids, index)
            if signal is None:
                armed = True
            elif armed and timestamps[index] >= next_allowed:
                direction, score, moves = signal
                candidates += 1
                row: dict[str, object] = {
                    "side": "buy" if direction > 0 else "sell",
                    "opened_at_utc": datetime.fromtimestamp(timestamps[index] / 1000, UTC).isoformat(),
                    "entry_price": round(mids[index] + direction * args.modeled_spread_pips * PIP_SIZE / 2, 6),
                    "score": score,
                }
                row.update({f"move_{seconds}s_pips": round(direction * moves[seconds], 3) for seconds in WINDOWS})
                row.update(simulate_exit(timestamps, mids, index, direction, args.modeled_spread_pips))
                trades.append(row)
                armed = False
                next_allowed = timestamps[index] + args.cooldown_seconds * 1000
            next_poll += args.poll_seconds * 1000
            index = bisect.bisect_left(timestamps, next_poll, index + 1)

    args.trades_output.parent.mkdir(parents=True, exist_ok=True)
    with args.trades_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(trades[0]) if trades else ["side"])
        writer.writeheader()
        writer.writerows(trades)
    monthly: dict[str, list[dict[str, object]]] = defaultdict(list)
    for trade in trades:
        monthly[str(trade["opened_at_utc"])[:7]].append(trade)
    summary = {
        "strategy_profile": "happy_gold_multiwindow_tick_score_shadow",
        "source": "Dukascopy XAUUSD ticks 2026-01-01 through 2026-04-14",
        "ticks_scanned": ticks_scanned, "poll_seconds": args.poll_seconds,
        "modeled_spread_pips": args.modeled_spread_pips, "cooldown_seconds": args.cooldown_seconds,
        "rearm_required": True, "thresholds_pips": THRESHOLDS,
        "full_period": metrics(trades),
        "by_month": {month: metrics(rows) for month, rows in sorted(monthly.items())},
        "limitations": [
            "Dukascopy is a proxy for the undisclosed original broker.",
            "Thresholds were derived from paired controls within this period; this replay measures false positives but is not an independent holdout.",
            "Signals are evaluated every five seconds, matching the EA timer configuration.",
        ],
    }
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
