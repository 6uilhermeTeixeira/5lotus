from __future__ import annotations

import argparse
import bisect
import csv
import json
import statistics
from array import array
from collections import defaultdict
from datetime import datetime
from pathlib import Path


WINDOWS_SECONDS = (1, 3, 5, 10, 30, 60, 300, 900, 3600)
GOLD_PIP_SIZE = 0.01


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract pre-entry microstructure features.")
    parser.add_argument("--reconstructed", type=Path, required=True)
    parser.add_argument("--ticks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    return parser.parse_args()


def completed_tick_files(root: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for marker in root.glob("xauusd-tick-*.csv.complete"):
        csv_path = marker.with_suffix("")
        parts = csv_path.stem.split("-")
        files["-".join(parts[2:5])] = csv_path
    return files


def load_ticks(path: Path) -> tuple[array, array, array]:
    timestamps = array("q")
    asks = array("d")
    bids = array("d")
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            timestamps.append(int(row["timestamp"]))
            asks.append(float(row["askPrice"]))
            bids.append(float(row["bidPrice"]))
    return timestamps, asks, bids


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def extract_window(
    timestamps: array,
    asks: array,
    bids: array,
    entry_index: int,
    entry_msc: int,
    seconds: int,
    direction: int,
) -> dict[str, float | int | None]:
    left = bisect.bisect_left(timestamps, entry_msc - seconds * 1000)
    right = bisect.bisect_right(timestamps, entry_msc)
    if left >= right:
        return {}
    mids = [(asks[index] + bids[index]) / 2 for index in range(left, right)]
    spreads = [asks[index] - bids[index] for index in range(left, right)]
    changes = [mids[index] - mids[index - 1] for index in range(1, len(mids))]
    directional_changes = [change * direction for change in changes if change != 0]
    entry_mid = (asks[entry_index] + bids[entry_index]) / 2
    start_mid = mids[0]
    minimum = min(mids)
    maximum = max(mids)
    range_size = maximum - minimum
    return {
        "tick_count": right - left,
        "tick_rate_per_second": (right - left) / seconds,
        "directional_move_pips": direction * (entry_mid - start_mid) / GOLD_PIP_SIZE,
        "range_pips": range_size / GOLD_PIP_SIZE,
        "realized_variation_pips": sum(abs(change) for change in changes) / GOLD_PIP_SIZE,
        "directional_tick_ratio": (
            sum(change > 0 for change in directional_changes) / len(directional_changes)
            if directional_changes else None
        ),
        "median_spread_pips": median(spreads) / GOLD_PIP_SIZE if spreads else None,
        "entry_range_location": (entry_mid - minimum) / range_size if range_size else 0.5,
    }


def main() -> None:
    args = parse_args()
    tick_files = completed_tick_files(args.ticks)
    selected: list[dict[str, str]] = []
    with args.reconstructed.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["confidence"] in {"high", "medium"}:
                selected.append(row)

    by_date: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in selected:
        by_date[row["entry_time_utc"][:10]].append(row)

    features: list[dict[str, object]] = []
    for utc_date, trades in sorted(by_date.items()):
        tick_file = tick_files.get(utc_date)
        if tick_file is None:
            continue
        timestamps, asks, bids = load_ticks(tick_file)
        for trade in trades:
            entry_msc = int(datetime.fromisoformat(trade["entry_time_utc"]).timestamp() * 1000)
            entry_index = bisect.bisect_left(timestamps, entry_msc)
            if entry_index >= len(timestamps):
                continue
            direction = 1 if trade["action"] == "buy" else -1
            entry_spread = asks[entry_index] - bids[entry_index]
            output: dict[str, object] = {
                "source_row": int(trade["source_row"]),
                "confidence": trade["confidence"],
                "action": trade["action"],
                "entry_time_utc": trade["entry_time_utc"],
                "entry_spread_pips": round(entry_spread / GOLD_PIP_SIZE, 6),
            }
            window_values: dict[int, dict[str, float | int | None]] = {}
            for seconds in WINDOWS_SECONDS:
                values = extract_window(
                    timestamps, asks, bids, entry_index, entry_msc, seconds, direction
                )
                window_values[seconds] = values
                for name, value in values.items():
                    output[f"pre_{seconds}s_{name}"] = round(value, 6) if isinstance(value, float) else value
            rate_5 = window_values[5].get("tick_rate_per_second")
            rate_10 = window_values[10].get("tick_rate_per_second")
            output["tick_rate_acceleration_5s_vs_10s"] = (
                round(float(rate_5) / float(rate_10), 6) if rate_5 and rate_10 else None
            )
            features.append(output)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(features[0]))
        writer.writeheader()
        writer.writerows(features)

    groups: dict[str, list[dict[str, object]]] = {
        "all": features,
        "buy": [row for row in features if row["action"] == "buy"],
        "sell": [row for row in features if row["action"] == "sell"],
        "high": [row for row in features if row["confidence"] == "high"],
    }
    summary_groups: dict[str, object] = {}
    for group_name, rows in groups.items():
        metrics: dict[str, object] = {"trades": len(rows)}
        for seconds in WINDOWS_SECONDS:
            move_key = f"pre_{seconds}s_directional_move_pips"
            rate_key = f"pre_{seconds}s_tick_rate_per_second"
            spread_key = f"pre_{seconds}s_median_spread_pips"
            moves = [float(row[move_key]) for row in rows if row.get(move_key) is not None]
            rates = [float(row[rate_key]) for row in rows if row.get(rate_key) is not None]
            spreads = [float(row[spread_key]) for row in rows if row.get(spread_key) is not None]
            metrics[f"pre_{seconds}s"] = {
                "median_directional_move_pips": median(moves),
                "directional_move_positive_percent": (
                    round(100 * sum(value > 0 for value in moves) / len(moves), 3) if moves else None
                ),
                "median_tick_rate_per_second": median(rates),
                "median_spread_pips": median(spreads),
            }
        accelerations = [
            float(row["tick_rate_acceleration_5s_vs_10s"])
            for row in rows if row.get("tick_rate_acceleration_5s_vs_10s") is not None
        ]
        metrics["median_tick_rate_acceleration_5s_vs_10s"] = median(accelerations)
        summary_groups[group_name] = metrics

    summary = {
        "method": "Tick microstructure immediately before reconstructed entries",
        "gold_pip_size": GOLD_PIP_SIZE,
        "selected_confidence": ["high", "medium"],
        "feature_rows": len(features),
        "groups": summary_groups,
        "limitation": "Entry cases alone describe the signal but do not establish discrimination versus non-entry controls.",
    }
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
