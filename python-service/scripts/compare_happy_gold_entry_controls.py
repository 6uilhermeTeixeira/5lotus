from __future__ import annotations

import argparse
import bisect
import csv
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from extract_happy_gold_entry_features import (
    WINDOWS_SECONDS,
    completed_tick_files,
    extract_window,
    load_ticks,
)


CONTROL_OFFSETS_MINUTES = (-55, -37, -19, 19, 37, 55)
EXCLUSION_MILLISECONDS = 3 * 60 * 1000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Happy Gold entries with paired controls.")
    parser.add_argument("--reconstructed", type=Path, required=True)
    parser.add_argument("--ticks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--controls-per-trade", type=int, default=5)
    return parser.parse_args()


def empirical_auc(positive: list[float], negative: list[float]) -> float | None:
    if not positive or not negative:
        return None
    wins = sum(p > n for p in positive for n in negative)
    ties = sum(p == n for p in positive for n in negative)
    return (wins + 0.5 * ties) / (len(positive) * len(negative))


def best_threshold(positive: list[float], negative: list[float]) -> dict[str, float] | None:
    if not positive or not negative:
        return None
    candidates = sorted(set(positive + negative))
    best: tuple[float, float, float, float] | None = None
    for threshold in candidates:
        sensitivity = sum(value >= threshold for value in positive) / len(positive)
        specificity = sum(value < threshold for value in negative) / len(negative)
        balanced_accuracy = (sensitivity + specificity) / 2
        candidate = (balanced_accuracy, sensitivity, specificity, threshold)
        if best is None or candidate > best:
            best = candidate
    assert best is not None
    return {
        "threshold": round(best[3], 6),
        "sensitivity": round(best[1], 6),
        "specificity": round(best[2], 6),
        "balanced_accuracy": round(best[0], 6),
    }


def leave_one_day_out(rows: list[dict[str, object]], key: str) -> dict[str, float] | None:
    dates = sorted({str(row["utc_date"]) for row in rows})
    true_positive = false_negative = true_negative = false_positive = 0
    folds = 0
    for date in dates:
        training_entries = [
            float(row[key]) for row in rows
            if row["utc_date"] != date and row["sample_type"] == "entry" and key in row
        ]
        training_controls = [
            float(row[key]) for row in rows
            if row["utc_date"] != date and row["sample_type"] == "control" and key in row
        ]
        rule = best_threshold(training_entries, training_controls)
        test = [row for row in rows if row["utc_date"] == date and key in row]
        if rule is None or not test:
            continue
        threshold = rule["threshold"]
        folds += 1
        for row in test:
            predicted_entry = float(row[key]) >= threshold
            if row["sample_type"] == "entry":
                true_positive += int(predicted_entry)
                false_negative += int(not predicted_entry)
            else:
                false_positive += int(predicted_entry)
                true_negative += int(not predicted_entry)
    if not folds or not (true_positive + false_negative) or not (true_negative + false_positive):
        return None
    sensitivity = true_positive / (true_positive + false_negative)
    specificity = true_negative / (true_negative + false_positive)
    return {
        "folds": folds,
        "sensitivity": round(sensitivity, 6),
        "specificity": round(specificity, 6),
        "balanced_accuracy": round((sensitivity + specificity) / 2, 6),
    }


def main() -> None:
    args = parse_args()
    tick_files = completed_tick_files(args.ticks)
    with args.reconstructed.open(encoding="utf-8", newline="") as handle:
        all_trades = list(csv.DictReader(handle))
    selected = [row for row in all_trades if row["confidence"] in {"high", "medium"}]

    actual_entries_by_date: dict[str, list[int]] = {}
    for trade in all_trades:
        value = trade.get("entry_time_utc", "")
        if not value:
            continue
        msc = int(datetime.fromisoformat(value).timestamp() * 1000)
        actual_entries_by_date.setdefault(value[:10], []).append(msc)

    rows: list[dict[str, object]] = []
    cache: dict[str, tuple] = {}
    for trade in selected:
        utc_date = trade["entry_time_utc"][:10]
        tick_file = tick_files.get(utc_date)
        if tick_file is None:
            continue
        if utc_date not in cache:
            cache[utc_date] = load_ticks(tick_file)
        timestamps, asks, bids = cache[utc_date]
        entry_msc = int(datetime.fromisoformat(trade["entry_time_utc"]).timestamp() * 1000)
        direction = 1 if trade["action"] == "buy" else -1
        samples = [("entry", 0, entry_msc)]
        controls = 0
        for offset in CONTROL_OFFSETS_MINUTES:
            control_msc = entry_msc + offset * 60 * 1000
            if datetime.fromtimestamp(control_msc / 1000).date().isoformat() != utc_date:
                continue
            if any(abs(control_msc - actual) < EXCLUSION_MILLISECONDS for actual in actual_entries_by_date.get(utc_date, [])):
                continue
            index = bisect.bisect_left(timestamps, control_msc)
            if index >= len(timestamps) or timestamps[index] - control_msc > 10_000:
                continue
            samples.append(("control", offset, int(timestamps[index])))
            controls += 1
            if controls >= args.controls_per_trade:
                break

        for sample_type, offset, sample_msc in samples:
            index = bisect.bisect_left(timestamps, sample_msc)
            output: dict[str, object] = {
                "source_row": int(trade["source_row"]),
                "confidence": trade["confidence"],
                "action": trade["action"],
                "sample_type": sample_type,
                "offset_minutes": offset,
                "sample_time_utc": datetime.fromtimestamp(sample_msc / 1000, timezone.utc).isoformat(),
                "utc_date": utc_date,
            }
            for seconds in WINDOWS_SECONDS:
                values = extract_window(timestamps, asks, bids, index, sample_msc, seconds, direction)
                for name, value in values.items():
                    output[f"pre_{seconds}s_{name}"] = round(value, 6) if isinstance(value, float) else value
            rows.append(output)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    entries = [row for row in rows if row["sample_type"] == "entry"]
    controls = [row for row in rows if row["sample_type"] == "control"]
    comparisons: dict[str, object] = {}
    for seconds in WINDOWS_SECONDS:
        key = f"pre_{seconds}s_directional_move_pips"
        positive = [float(row[key]) for row in entries if key in row]
        negative = [float(row[key]) for row in controls if key in row]
        comparisons[key] = {
            "entry_median": statistics.median(positive),
            "control_median": statistics.median(negative),
            "auc": round(empirical_auc(positive, negative) or 0, 6),
            "best_exploratory_rule": best_threshold(positive, negative),
            "leave_one_day_out": leave_one_day_out(rows, key),
        }

    summary = {
        "method": "Same-day paired controls using the matched trade direction",
        "control_offsets_minutes": CONTROL_OFFSETS_MINUTES,
        "exclusion_minutes_around_any_entry": EXCLUSION_MILLISECONDS // 60_000,
        "entries": len(entries),
        "controls": len(controls),
        "controls_per_entry_median": statistics.median(
            [sum(row["sample_type"] == "control" and row["source_row"] == entry["source_row"] for row in rows) for entry in entries]
        ),
        "comparisons": comparisons,
        "limitation": "Thresholds are exploratory and in-sample; controls from the same day are correlated and require out-of-sample validation.",
    }
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
