"""Stress the frozen Bot 21 lifecycle across spread and entry-latency scenarios."""

from __future__ import annotations

import argparse
import bisect
import csv
import json
from datetime import UTC, datetime
from pathlib import Path


PIP_SIZE = 0.01
USD_PER_PIP = 0.10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--signals", type=Path, required=True)
    parser.add_argument("--ticks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def tick_files(root: Path) -> dict[str, Path]:
    return {
        "-".join(marker.with_suffix("").stem.split("-")[2:5]): marker.with_suffix("")
        for marker in root.glob("xauusd-tick-*.csv.complete")
    }


def load_ticks(path: Path) -> tuple[list[int], list[float]]:
    timestamps: list[int] = []
    mids: list[float] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            timestamps.append(int(row["timestamp"]))
            mids.append((float(row["askPrice"]) + float(row["bidPrice"])) / 2)
    return timestamps, mids


def simulate(
    signal: dict[str, str], timestamps: list[int], mids: list[float], spread_pips: float, latency_msc: int
) -> dict[str, object]:
    signal_msc = int(datetime.fromisoformat(signal["opened_at_utc"]).timestamp() * 1000)
    left = bisect.bisect_left(timestamps, signal_msc + latency_msc)
    side = signal["side"]
    direction = 1 if side == "buy" else -1
    half_spread = spread_pips * PIP_SIZE / 2
    entry = mids[left] + direction * half_spread
    stop = entry - direction * 60 * PIP_SIZE
    target = entry + direction * 1000 * PIP_SIZE
    best = mids[left] - direction * half_spread
    end = bisect.bisect_right(timestamps, timestamps[left] + 60_000, left)
    exit_index = end - 1
    exit_price = mids[exit_index] - direction * half_spread
    reason = "time"
    for index in range(left, end):
        executable = mids[index] - direction * half_spread
        best = max(best, executable) if side == "buy" else min(best, executable)
        favorable = direction * (best - entry) / PIP_SIZE
        if favorable >= 40:
            trailing = best - direction * 20 * PIP_SIZE
            stop = max(stop, trailing) if side == "buy" else min(stop, trailing)
            breakeven = entry + direction * PIP_SIZE
            stop = max(stop, breakeven) if side == "buy" else min(stop, breakeven)
        stopped = executable <= stop if side == "buy" else executable >= stop
        targeted = executable >= target if side == "buy" else executable <= target
        if stopped or targeted:
            exit_index, exit_price = index, executable
            reason = "stop" if stopped else "target"
            break
    pnl_pips = direction * (exit_price - entry) / PIP_SIZE
    return {
        "opened_at_utc": datetime.fromtimestamp(timestamps[left] / 1000, UTC).isoformat(),
        "closed_at_utc": datetime.fromtimestamp(timestamps[exit_index] / 1000, UTC).isoformat(),
        "side": side,
        "entry_price": round(entry, 6), "exit_price": round(exit_price, 6),
        "exit_reason": reason,
        "duration_seconds": round((timestamps[exit_index] - timestamps[left]) / 1000, 3),
        "pnl_pips": round(pnl_pips, 3), "net_pnl": round(pnl_pips * USD_PER_PIP, 2),
    }


def metrics(rows: list[dict[str, object]]) -> dict[str, object]:
    wins = [row for row in rows if float(row["net_pnl"]) > 0]
    losses = [row for row in rows if float(row["net_pnl"]) < 0]
    gross_profit = sum(float(row["net_pnl"]) for row in wins)
    gross_loss = -sum(float(row["net_pnl"]) for row in losses)
    equity = peak = drawdown = 0.0
    for row in sorted(rows, key=lambda item: str(item["opened_at_utc"])):
        equity += float(row["net_pnl"])
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return {
        "trades": len(rows), "wins": len(wins), "losses": len(losses),
        "win_rate_pct": round(100 * len(wins) / len(rows), 3) if rows else None,
        "net_pnl": round(equity, 2),
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else None,
        "max_drawdown": round(drawdown, 2),
    }


def main() -> None:
    args = parse_args()
    with args.signals.open(encoding="utf-8", newline="") as handle:
        signals = list(csv.DictReader(handle))
    grouped: dict[str, list[dict[str, str]]] = {}
    for signal in signals:
        grouped.setdefault(signal["opened_at_utc"][:10], []).append(signal)
    files = tick_files(args.ticks)
    scenarios = {(spread, latency): [] for spread in (5, 10, 15, 20) for latency in (0, 250, 500, 1000)}
    for date, date_signals in sorted(grouped.items()):
        timestamps, mids = load_ticks(files[date])
        for signal in date_signals:
            for (spread, latency), rows in scenarios.items():
                rows.append(simulate(signal, timestamps, mids, spread, latency))
    matrix = {
        f"spread_{spread}_latency_{latency}ms": metrics(rows)
        for (spread, latency), rows in scenarios.items()
    }
    profitable = [name for name, result in matrix.items() if float(result["profit_factor"] or 0) > 1]
    report = {
        "method": "Frozen Bot 21 timestamps and lifecycle; only modeled spread and entry latency vary.",
        "period": "2026-04-15 through 2026-08-08",
        "signals": len(signals),
        "matrix": matrix,
        "profitable_scenarios": len(profitable),
        "total_scenarios": len(matrix),
        "decision": "execution_robust" if len(profitable) == len(matrix) else "execution_fragile",
        "limitations": [
            "Signal timestamps remain those generated with a modeled 10-pip spread.",
            "Latency changes entry price but does not recompute the upstream breakout timestamp.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
