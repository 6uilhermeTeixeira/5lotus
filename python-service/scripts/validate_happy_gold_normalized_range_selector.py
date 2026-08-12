"""Validate a fixed normalized M5-range selector across temporal partitions."""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import statistics
from datetime import datetime
from pathlib import Path


PIP_SIZE = 0.01


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--training-labels", type=Path, required=True)
    parser.add_argument("--signals-2025", type=Path, required=True)
    parser.add_argument("--candles-2025", type=Path, required=True)
    parser.add_argument("--signals-2026", type=Path, required=True)
    parser.add_argument("--candles-2026", type=Path, required=True)
    parser.add_argument("--labels-2026", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trades-output", type=Path)
    parser.add_argument("--labeled-start", default="2025-10-15T01:02:34.271000+00:00")
    return parser.parse_args()


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def load_candles(path: Path) -> tuple[list[datetime], list[dict[str, float]]]:
    times: list[datetime] = []
    rows: list[dict[str, float]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            times.append(datetime.fromisoformat(row["timestamp_utc"]))
            rows.append({key: float(row[key]) for key in ("high", "low", "close")})
    return times, rows


def normalized_prior_range(
    opened: datetime, candle_times: list[datetime], candles: list[dict[str, float]]
) -> float | None:
    bucket = opened.replace(minute=opened.minute // 5 * 5, second=0, microsecond=0)
    index = bisect.bisect_left(candle_times, bucket)
    history = candles[max(0, index - 15):index]
    if len(history) < 15:
        return None
    true_ranges = [
        max(
            row["high"] - row["low"],
            abs(row["high"] - previous["close"]),
            abs(row["low"] - previous["close"]),
        )
        for previous, row in zip(history[-15:-1], history[-14:])
    ]
    atr14_pips = statistics.fmean(true_ranges) / PIP_SIZE
    prior_range_pips = (history[-1]["high"] - history[-1]["low"]) / PIP_SIZE
    return prior_range_pips / atr14_pips if atr14_pips else None


def load_signals(path: Path, candle_path: Path) -> list[dict[str, object]]:
    candle_times, candles = load_candles(candle_path)
    result: list[dict[str, object]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            opened = datetime.fromisoformat(row["opened_at_utc"])
            ratio = normalized_prior_range(opened, candle_times, candles)
            if ratio is not None:
                result.append({**row, "opened": opened, "normalized_prior_m5_range": ratio})
    return result


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
        "trades": len(rows),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(100 * len(wins) / len(rows), 3) if rows else None,
        "net_pnl": round(equity, 2),
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else None,
        "max_drawdown": round(drawdown, 2),
    }


def main() -> None:
    args = parse_args()
    with args.training_labels.open(encoding="utf-8", newline="") as handle:
        matched_training = [row for row in csv.DictReader(handle) if row["matched_entry"] == "True"]
    training_ratios = [
        float(row["prior_m5_range_pips"]) / float(row["atr14_pips"])
        for row in matched_training
    ]
    threshold = percentile(training_ratios, 0.90)
    signals_2025 = load_signals(args.signals_2025, args.candles_2025)
    signals_2026 = load_signals(args.signals_2026, args.candles_2026)
    labeled_start = datetime.fromisoformat(args.labeled_start)

    with args.labels_2026.open(encoding="utf-8", newline="") as handle:
        labels_2026 = {row["opened_at_utc"]: row["matched_entry"] == "True" for row in csv.DictReader(handle)}

    def selected(rows: list[dict[str, object]]) -> list[dict[str, object]]:
        return [row for row in rows if float(row["normalized_prior_m5_range"]) <= threshold]

    partitions = {
        "2025_pre_label_holdout": [row for row in signals_2025 if row["opened"] < labeled_start],
        "2025_labeled_training_period": [row for row in signals_2025 if row["opened"] >= labeled_start],
        "2026_post_training_holdout": signals_2026,
    }
    report: dict[str, object] = {
        "method": "P90 of normalized prior-M5 range from matched 2025 entries, fixed before 2026 evaluation.",
        "feature": "prior_m5_range_pips / atr14_pips",
        "training_matched_entries": len(training_ratios),
        "threshold_lte": round(threshold, 9),
        "partitions": {},
    }
    output_partitions = report["partitions"]
    assert isinstance(output_partitions, dict)
    for name, rows in partitions.items():
        kept = selected(rows)
        output_partitions[name] = {"baseline": metrics(rows), "selected": metrics(kept)}
        if name == "2026_post_training_holdout":
            baseline_matched = sum(labels_2026.get(str(row["opened_at_utc"]), False) for row in rows)
            selected_matched = sum(labels_2026.get(str(row["opened_at_utc"]), False) for row in kept)
            output_partitions[name]["original_entry_correspondence"] = {
                "baseline_matched": baseline_matched,
                "selected_matched": selected_matched,
                "selected_precision_pct": round(100 * selected_matched / len(kept), 3) if kept else None,
                "matched_recall_pct": round(100 * selected_matched / baseline_matched, 3) if baseline_matched else None,
            }
    report["decision"] = (
        "candidate_only_if_both_temporal_holdouts_preserve_positive_expectancy_and_2026_pf_improves"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.trades_output:
        selected_trades = sorted(selected(signals_2025) + selected(signals_2026), key=lambda row: str(row["opened_at_utc"]))
        args.trades_output.parent.mkdir(parents=True, exist_ok=True)
        excluded_fields = {"opened", "normalized_prior_m5_range"}
        fieldnames = [key for key in selected_trades[0] if key not in excluded_fields]
        with args.trades_output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(selected_trades)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
