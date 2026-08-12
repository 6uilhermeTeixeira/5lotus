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
    max_hold_seconds: int
    break_even_trigger_pips: int
    break_even_offset_pips: int
    trailing_activation_pips: int
    trailing_distance_pips: int

    @property
    def name(self) -> str:
        return (
            f"stop{self.stop_pips}_hold{self.max_hold_seconds}_be{self.break_even_trigger_pips}"
            f"p{self.break_even_offset_pips}_trail{self.trailing_activation_pips}x{self.trailing_distance_pips}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Research tick-level exits for the structural selector.")
    parser.add_argument("--signals", type=Path, required=True)
    parser.add_argument("--candles", type=Path, required=True)
    parser.add_argument("--ticks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trades-output", type=Path)
    parser.add_argument("--selected-config", default="stop60_hold60_be40p1_trail40x20")
    parser.add_argument("--modeled-spread-pips", type=float, default=10)
    parser.add_argument("--horizon-seconds", type=int, default=120)
    return parser.parse_args()


def ema(values: list[float], period: int = 20) -> float:
    alpha = 2 / (period + 1)
    result = values[0]
    for value in values[1:]:
        result = alpha * value + (1 - alpha) * result
    return result


def select_signals(signals: list[dict[str, str]], candle_path: Path) -> list[dict[str, object]]:
    candle_times: list[datetime] = []
    closes: list[float] = []
    with candle_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            candle_times.append(datetime.fromisoformat(row["timestamp_utc"]))
            closes.append(float(row["close"]))
    selected: list[dict[str, object]] = []
    for signal in signals:
        opened = datetime.fromisoformat(signal["opened_at_utc"])
        bucket = opened.replace(minute=opened.minute // 5 * 5, second=0, microsecond=0)
        index = bisect.bisect_left(candle_times, bucket)
        history = closes[index - 30:index]
        direction = 1 if signal["side"] == "buy" else -1
        ema_gap = direction * (history[-1] - ema(history[-20:])) / PIP_SIZE
        extension = direction * (float(signal["entry_price"]) - float(signal["pivot"])) / PIP_SIZE
        if (
            opened.weekday() != 4
            and ema_gap >= 900
            and float(signal["context_move_pips"]) >= 1000
            and extension <= 50
        ):
            selected.append({
                "opened": opened, "opened_msc": int(opened.timestamp() * 1000),
                "side": signal["side"], "entry": float(signal["entry_price"]),
            })
    return selected


def tick_files(root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for marker in root.glob("xauusd-tick-*.csv.complete"):
        path = marker.with_suffix("")
        result["-".join(path.stem.split("-")[2:5])] = path
    return result


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
    signal: dict[str, object], config: ExitConfig,
    timestamps: list[int], bids: list[float], asks: list[float], horizon_seconds: int,
) -> dict[str, object]:
    opened_msc = int(signal["opened_msc"])
    left = bisect.bisect_left(timestamps, opened_msc)
    right = bisect.bisect_right(timestamps, opened_msc + min(horizon_seconds, config.max_hold_seconds) * 1000)
    side = str(signal["side"])
    entry = float(signal["entry"])
    direction = 1 if side == "buy" else -1
    stop = entry - direction * config.stop_pips * PIP_SIZE
    best = bids[left] if side == "buy" else asks[left]
    exit_price = bids[right - 1] if side == "buy" else asks[right - 1]
    exit_msc = timestamps[right - 1]
    reason = "time"
    for index in range(left, right):
        executable = bids[index] if side == "buy" else asks[index]
        best = max(best, executable) if side == "buy" else min(best, executable)
        favorable = direction * (best - entry) / PIP_SIZE
        if favorable >= config.trailing_activation_pips:
            candidate = best - direction * config.trailing_distance_pips * PIP_SIZE
            stop = max(stop, candidate) if side == "buy" else min(stop, candidate)
        if favorable >= config.break_even_trigger_pips:
            candidate = entry + direction * config.break_even_offset_pips * PIP_SIZE
            stop = max(stop, candidate) if side == "buy" else min(stop, candidate)
        stopped = executable <= stop if side == "buy" else executable >= stop
        if stopped:
            exit_price, exit_msc, reason = executable, timestamps[index], "stop"
            break
    pnl_pips = direction * (exit_price - entry) / PIP_SIZE
    return {
        "opened_at_utc": datetime.fromtimestamp(opened_msc / 1000, UTC).isoformat(),
        "closed_at_utc": datetime.fromtimestamp(exit_msc / 1000, UTC).isoformat(),
        "quarter": f"{datetime.fromtimestamp(opened_msc / 1000, UTC).year}-Q{(datetime.fromtimestamp(opened_msc / 1000, UTC).month - 1) // 3 + 1}",
        "side": side, "config": config.name, "entry_price": entry, "exit_price": exit_price, "exit_reason": reason,
        "duration_seconds": round((exit_msc - opened_msc) / 1000, 3),
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
        "net_pnl": round(sum(float(row["net_pnl"]) for row in rows), 2),
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else None,
        "max_drawdown": round(drawdown, 2),
    }


def main() -> None:
    args = parse_args()
    with args.signals.open(encoding="utf-8", newline="") as handle:
        signals = select_signals(list(csv.DictReader(handle)), args.candles)
    files = tick_files(args.ticks)
    by_date: dict[str, list[dict[str, object]]] = {}
    for signal in signals:
        by_date.setdefault(str(signal["opened"])[:10], []).append(signal)
    configs = [
        ExitConfig(stop, hold, be, 1, trail, distance)
        for stop in (60, 120, 240)
        for hold in (30, 60)
        for be in (10, 20, 40)
        for trail, distance in ((40, 20), (80, 40), (120, 60))
    ]
    results: list[dict[str, object]] = []
    for date, date_signals in sorted(by_date.items()):
        timestamps, bids, asks = load_quotes(files[date], args.modeled_spread_pips)
        for signal in date_signals:
            for config in configs:
                results.append(simulate(signal, config, timestamps, bids, asks, args.horizon_seconds))
    summaries: list[dict[str, object]] = []
    quarters = sorted({str(row["quarter"]) for row in results})
    for config in configs:
        rows = [row for row in results if row["config"] == config.name]
        full = metrics(rows)
        quarter_metrics = {quarter: metrics([row for row in rows if row["quarter"] == quarter]) for quarter in quarters}
        profitable_quarters = sum(float(value["net_pnl"]) > 0 for value in quarter_metrics.values())
        summaries.append({
            "config": asdict(config), "name": config.name, "full_year": full,
            "profitable_quarters": profitable_quarters, "by_quarter": quarter_metrics,
        })
    ranked = sorted(
        summaries,
        key=lambda row: (
            int(row["profitable_quarters"]),
            float(row["full_year"]["profit_factor"] or 0),  # type: ignore[index]
            float(row["full_year"]["net_pnl"]),  # type: ignore[index]
        ),
        reverse=True,
    )
    report = {
        "method": (
            "Tick-executable exit grid on fixed structural signals; ranking prioritizes "
            "profitable quarters before full-period PF."
        ),
        "signals": len(signals), "configs": len(configs),
        "modeled_spread_pips": args.modeled_spread_pips,
        "top_10": ranked[:10],
        "warning": "This is exit research on a small selected sample, not authorization for live execution.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.trades_output:
        selected = [row for row in results if row["config"] == args.selected_config]
        if not selected:
            raise ValueError(f"selected config not found: {args.selected_config}")
        args.trades_output.parent.mkdir(parents=True, exist_ok=True)
        with args.trades_output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(selected[0]))
            writer.writeheader()
            writer.writerows(selected)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
