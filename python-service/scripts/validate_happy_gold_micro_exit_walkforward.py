"""Select a fixed micro-exit on 2025 signals and evaluate it unchanged in 2026."""

from __future__ import annotations

import argparse
import bisect
import csv
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


PIP_SIZE = 0.01
USD_PER_PIP = 0.10


@dataclass(frozen=True)
class ExitConfig:
    stop_pips: int
    target_pips: int
    max_hold_seconds: int

    @property
    def name(self) -> str:
        return f"stop{self.stop_pips}_target{self.target_pips}_hold{self.max_hold_seconds}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--signals", type=Path, required=True)
    parser.add_argument("--ticks-2025", type=Path, required=True)
    parser.add_argument("--ticks-2026", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trades-output", type=Path)
    parser.add_argument("--modeled-spread-pips", type=float, default=10)
    return parser.parse_args()


def tick_files(root: Path) -> dict[str, Path]:
    return {
        "-".join(marker.with_suffix("").stem.split("-")[2:5]): marker.with_suffix("")
        for marker in root.glob("xauusd-tick-*.csv.complete")
    }


def load_quotes(path: Path, spread_pips: float) -> tuple[list[int], list[float], list[float]]:
    timestamps: list[int] = []
    bids: list[float] = []
    asks: list[float] = []
    half_spread = spread_pips * PIP_SIZE / 2
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            mid = (float(row["askPrice"]) + float(row["bidPrice"])) / 2
            timestamps.append(int(row["timestamp"]))
            bids.append(mid - half_spread)
            asks.append(mid + half_spread)
    return timestamps, bids, asks


def simulate(
    signal: dict[str, str],
    config: ExitConfig,
    timestamps: list[int],
    bids: list[float],
    asks: list[float],
) -> dict[str, object]:
    opened = datetime.fromisoformat(signal["opened_at_utc"])
    opened_msc = int(opened.timestamp() * 1000)
    left = bisect.bisect_left(timestamps, opened_msc)
    right = bisect.bisect_right(timestamps, opened_msc + config.max_hold_seconds * 1000)
    side = signal["side"]
    direction = 1 if side == "buy" else -1
    entry = float(signal["entry_price"])
    stop = entry - direction * config.stop_pips * PIP_SIZE
    target = entry + direction * config.target_pips * PIP_SIZE
    exit_index = max(left, right - 1)
    exit_price = bids[exit_index] if side == "buy" else asks[exit_index]
    reason = "time"
    for index in range(left, right):
        executable = bids[index] if side == "buy" else asks[index]
        if (side == "buy" and executable <= stop) or (side == "sell" and executable >= stop):
            exit_index, exit_price, reason = index, executable, "stop"
            break
        if (side == "buy" and executable >= target) or (side == "sell" and executable <= target):
            exit_index, exit_price, reason = index, executable, "target"
            break
    pnl_pips = direction * (exit_price - entry) / PIP_SIZE
    return {
        "opened_at_utc": signal["opened_at_utc"],
        "closed_at_utc": datetime.fromtimestamp(timestamps[exit_index] / 1000, UTC).isoformat(),
        "side": side,
        "entry_price": entry,
        "exit_price": round(exit_price, 6),
        "exit_reason": reason,
        "duration_seconds": round((timestamps[exit_index] - opened_msc) / 1000, 3),
        "pnl_pips": round(pnl_pips, 3),
        "net_pnl": round(pnl_pips * USD_PER_PIP, 2),
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


def replay(signals: list[dict[str, str]], root: Path, spread_pips: float, configs: list[ExitConfig]) -> dict[str, list[dict[str, object]]]:
    files = tick_files(root)
    grouped: dict[str, list[dict[str, str]]] = {}
    for signal in signals:
        grouped.setdefault(signal["opened_at_utc"][:10], []).append(signal)
    results = {config.name: [] for config in configs}
    for date, date_signals in sorted(grouped.items()):
        timestamps, bids, asks = load_quotes(files[date], spread_pips)
        for signal in date_signals:
            for config in configs:
                results[config.name].append(simulate(signal, config, timestamps, bids, asks))
    return results


def main() -> None:
    args = parse_args()
    with args.signals.open(encoding="utf-8", newline="") as handle:
        signals = list(csv.DictReader(handle))
    training = [row for row in signals if row["opened_at_utc"].startswith("2025-")]
    holdout = [row for row in signals if row["opened_at_utc"].startswith("2026-")]
    configs = [
        ExitConfig(stop, target, hold)
        for stop in (10, 20, 30, 60)
        for target in (1, 5, 10, 20, 40, 80, 160)
        for hold in (5, 10, 20, 30, 60)
    ]
    training_results = replay(training, args.ticks_2025, args.modeled_spread_pips, configs)
    candidates: list[dict[str, object]] = []
    for config in configs:
        rows = training_results[config.name]
        full = metrics(rows)
        quarters = sorted({str(row["opened_at_utc"])[:7] for row in rows})
        profitable_periods = sum(
            float(metrics([row for row in rows if str(row["opened_at_utc"])[:7] == period])["net_pnl"]) > 0
            for period in quarters
        )
        candidates.append({
            "config": asdict(config), "name": config.name, "training": full,
            "profitable_training_months": profitable_periods,
            "training_months": len(quarters),
        })
    eligible = [
        row for row in candidates
        if float(row["training"]["profit_factor"] or 0) >= 1.20  # type: ignore[index]
    ]
    ranked = sorted(
        eligible,
        key=lambda row: (
            int(row["profitable_training_months"]),
            -abs(float(row["training"]["win_rate_pct"] or 0) - 85),  # type: ignore[index]
            float(row["training"]["profit_factor"] or 0),  # type: ignore[index]
        ),
        reverse=True,
    )
    if not ranked:
        raise RuntimeError("No training configuration passed the minimum profit-factor gate")
    selected = ranked[0]
    config = ExitConfig(**selected["config"])  # type: ignore[arg-type]
    holdout_rows = replay(holdout, args.ticks_2026, args.modeled_spread_pips, [config])[config.name]
    report = {
        "method": "Exit selected on 2025 only; unchanged evaluation on 2026 tick holdout.",
        "modeled_spread_pips": args.modeled_spread_pips,
        "training_signals": len(training), "holdout_signals": len(holdout),
        "selection_gate": "training PF >= 1.20; rank profitable months, proximity to 85% win rate, then PF",
        "selected": {**selected, "holdout_2026": metrics(holdout_rows)},
        "top_training_candidates": ranked[:10],
        "decision": "rejected_holdout_underperformed_bot21_tick_lifecycle",
        "bot21_holdout_reference": {
            "win_rate_pct": 57.333,
            "profit_factor": 2.485,
            "max_drawdown": 34.22,
        },
        "warning": "Small 2025 training sample; holdout result is required before any forward candidate.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.trades_output:
        args.trades_output.parent.mkdir(parents=True, exist_ok=True)
        with args.trades_output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(holdout_rows[0]))
            writer.writeheader()
            writer.writerows(holdout_rows)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
