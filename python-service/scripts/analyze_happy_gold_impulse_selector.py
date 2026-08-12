"""Compare known Happy Gold entries with every multiwindow impulse candidate."""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--reconstructed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--tolerance-seconds", type=int, default=10)
    return parser.parse_args()


def auc(positive: list[float], negative: list[float]) -> float | None:
    if not positive or not negative:
        return None
    ordered = sorted((value, 1) for value in positive) + sorted((value, 0) for value in negative)
    ordered.sort(key=lambda item: item[0])
    rank_sum = 0.0
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][0] == ordered[index][0]:
            end += 1
        average_rank = (index + 1 + end) / 2
        rank_sum += average_rank * sum(label for _, label in ordered[index:end])
        index = end
    return (rank_sum - len(positive) * (len(positive) + 1) / 2) / (len(positive) * len(negative))


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] if low == high else ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def main() -> None:
    args = parse_args()
    with args.candidates.open(encoding="utf-8", newline="") as handle:
        candidates = list(csv.DictReader(handle))
    with args.reconstructed.open(encoding="utf-8", newline="") as handle:
        known = [row for row in csv.DictReader(handle) if row["confidence"] in {"high", "medium"}]

    by_side: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for index, candidate in enumerate(candidates):
        timestamp = int(datetime.fromisoformat(candidate["opened_at_utc"]).timestamp() * 1000)
        by_side[candidate["side"]].append((timestamp, index))
    for values in by_side.values():
        values.sort()

    matched_candidate_indexes: set[int] = set()
    matched_known = 0
    tolerance_msc = args.tolerance_seconds * 1000
    for entry in known:
        timestamp = int(datetime.fromisoformat(entry["entry_time_utc"]).timestamp() * 1000)
        values = by_side[entry["action"]]
        times = [item[0] for item in values]
        left = bisect.bisect_left(times, timestamp - tolerance_msc)
        right = bisect.bisect_right(times, timestamp + tolerance_msc)
        if left < right:
            best = min(values[left:right], key=lambda item: abs(item[0] - timestamp))
            matched_candidate_indexes.add(best[1])
            matched_known += 1

    rows: list[dict[str, object]] = []
    for index, candidate in enumerate(candidates):
        opened = datetime.fromisoformat(candidate["opened_at_utc"])
        moves = {seconds: float(candidate[f"move_{seconds}s_pips"]) for seconds in (5, 10, 30, 60, 300, 900)}
        rows.append({
            "opened_at_utc": candidate["opened_at_utc"], "side": candidate["side"],
            "matched_entry": index in matched_candidate_indexes,
            "hour_utc": opened.hour + opened.minute / 60,
            "minute": opened.minute, "second": opened.second,
            "score": float(candidate["score"]),
            **{f"move_{seconds}s_pips": value for seconds, value in moves.items()},
            "ratio_5_60": moves[5] / moves[60] if moves[60] else 0,
            "ratio_10_60": moves[10] / moves[60] if moves[60] else 0,
            "ratio_30_60": moves[30] / moves[60] if moves[60] else 0,
            "ratio_60_300": moves[60] / moves[300] if moves[300] else 0,
            "ratio_300_900": moves[300] / moves[900] if moves[900] else 0,
            "acceleration_60_vs_prior_240": moves[60] / max(moves[300] - moves[60], 1),
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    positives = [row for row in rows if row["matched_entry"]]
    negatives = [row for row in rows if not row["matched_entry"]]
    fields = [key for key in rows[0] if key not in {"opened_at_utc", "side", "matched_entry", "minute", "second"}]
    comparisons: dict[str, object] = {}
    for field in fields:
        positive = [float(row[field]) for row in positives]
        negative = [float(row[field]) for row in negatives]
        metric_auc = auc(positive, negative)
        comparisons[field] = {
            "matched_median": round(statistics.median(positive), 6) if positive else None,
            "unmatched_median": round(statistics.median(negative), 6) if negative else None,
            "auc": round(metric_auc, 6) if metric_auc is not None else None,
            "separation": round(max(metric_auc, 1 - metric_auc), 6) if metric_auc is not None else None,
            "matched_p10": round(percentile(positive, .1), 6) if positive else None,
            "matched_p90": round(percentile(positive, .9), 6) if positive else None,
        }
    ranked = sorted(comparisons.items(), key=lambda item: float(item[1]["separation"] or 0), reverse=True)
    summary = {
        "method": "Known high/medium-confidence entries matched to exhaustive multiwindow candidates by side and time.",
        "tolerance_seconds": args.tolerance_seconds,
        "known_entries": len(known), "known_entries_with_candidate": matched_known,
        "candidate_rows": len(candidates), "matched_candidate_rows": len(positives),
        "candidate_precision_pct": round(100 * len(positives) / len(candidates), 4) if candidates else 0,
        "top_discriminators": [{"feature": name, **values} for name, values in ranked[:12]],
        "limitations": [
            "Candidate thresholds were derived from this labeled period.",
            "A temporal match is evidence of correspondence, not proof of the original internal signal.",
            "Unmatched candidates greatly outnumber entries; AUC alone does not establish usable precision.",
        ],
    }
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
