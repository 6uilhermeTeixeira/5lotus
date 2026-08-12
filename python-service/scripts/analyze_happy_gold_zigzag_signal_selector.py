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
    parser = argparse.ArgumentParser(description="Label annual ZigZag-context signals against reconstructed entries.")
    parser.add_argument("--signals", type=Path, required=True)
    parser.add_argument("--reconstructed", type=Path, required=True)
    parser.add_argument("--forward", type=Path, required=True)
    parser.add_argument("--candles", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--tolerance-seconds", type=float, default=60)
    return parser.parse_args()


def pct(numerator: int, denominator: int) -> float | None:
    return round(100 * numerator / denominator, 3) if denominator else None


def median(rows: list[dict[str, object]], field: str) -> float | None:
    values = [float(row[field]) for row in rows]
    return round(statistics.median(values), 3) if values else None


def ema(values: list[float], period: int) -> float:
    alpha = 2 / (period + 1)
    result = values[0]
    for value in values[1:]:
        result = alpha * value + (1 - alpha) * result
    return result


def auc(rows: list[dict[str, object]], field: str) -> dict[str, object]:
    positives = [float(row[field]) for row in rows if row["matched_entry"]]
    negatives = [float(row[field]) for row in rows if not row["matched_entry"]]
    if not positives or not negatives:
        return {"auc": None, "preferred_direction": None}
    favorable = ties = 0
    for positive in positives:
        for negative in negatives:
            favorable += positive > negative
            ties += positive == negative
    raw = (favorable + .5 * ties) / (len(positives) * len(negatives))
    return {
        "auc": round(max(raw, 1 - raw), 4),
        "preferred_direction": "higher" if raw >= .5 else "lower",
    }


def main() -> None:
    args = parse_args()
    with args.signals.open(encoding="utf-8", newline="") as handle:
        signals = list(csv.DictReader(handle))
    with args.reconstructed.open(encoding="utf-8", newline="") as handle:
        entries = [
            row for row in csv.DictReader(handle)
            if row["confidence"] in {"high", "medium"}
        ]
    outcomes: dict[int, float] = {}
    with args.forward.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            outcomes[int(row["source_row"])] = float(row["profit_usd"])

    candle_times: list[datetime] = []
    candle_rows: list[dict[str, float]] = []
    with args.candles.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            candle_times.append(datetime.fromisoformat(row["timestamp_utc"]))
            candle_rows.append({name: float(row[name]) for name in ("open", "high", "low", "close")})

    entry_times = [datetime.fromisoformat(row["entry_time_utc"]) for row in entries]
    coverage_start, coverage_end = min(entry_times), max(entry_times)
    covered = [
        row for row in signals
        if coverage_start <= datetime.fromisoformat(row["opened_at_utc"]) <= coverage_end
    ]
    available = set(range(len(covered)))
    matches: dict[int, tuple[dict[str, str], float]] = {}
    for entry in sorted(entries, key=lambda row: row["entry_time_utc"]):
        entry_time = datetime.fromisoformat(entry["entry_time_utc"])
        candidates = [
            (abs((datetime.fromisoformat(covered[index]["opened_at_utc"]) - entry_time).total_seconds()), index)
            for index in available if covered[index]["side"] == entry["action"]
        ]
        if not candidates:
            continue
        distance, index = min(candidates)
        if distance <= args.tolerance_seconds:
            matches[index] = (entry, distance)
            available.remove(index)

    labeled: list[dict[str, object]] = []
    for index, signal in enumerate(covered):
        opened = datetime.fromisoformat(signal["opened_at_utc"])
        direction = 1 if signal["side"] == "buy" else -1
        extension_pips = direction * (float(signal["entry_price"]) - float(signal["pivot"])) / PIP_SIZE
        entry, distance = matches.get(index, ({}, 0.0))
        source_row = int(entry["source_row"]) if entry else None
        candle_bucket = opened.replace(minute=opened.minute // 5 * 5, second=0, microsecond=0)
        candle_index = bisect.bisect_left(candle_times, candle_bucket)
        history = candle_rows[max(0, candle_index - 100):candle_index]
        closes = [row["close"] for row in history]
        true_ranges = [
            max(row["high"] - row["low"], abs(row["high"] - previous["close"]), abs(row["low"] - previous["close"]))
            for previous, row in zip(history[-15:-1], history[-14:])
        ]
        atr14 = statistics.fmean(true_ranges) if true_ranges else 0.0
        ema20 = ema(closes[-20:], 20) if len(closes) >= 20 else closes[-1]
        previous_ema20 = ema(closes[-21:-1], 20) if len(closes) >= 21 else ema20
        output = {
            "opened_at_utc": signal["opened_at_utc"],
            "month": opened.strftime("%Y-%m"),
            "weekday": opened.weekday(),
            "hour_utc": opened.hour,
            "minute": opened.minute,
            "side": signal["side"],
            "context_move_pips": float(signal["context_move_pips"]),
            "pivot_extension_pips": round(extension_pips, 3),
            "atr14_pips": round(atr14 / PIP_SIZE, 3),
            "directional_ema20_gap_pips": round(direction * (closes[-1] - ema20) / PIP_SIZE, 3),
            "directional_ema20_slope_pips": round(direction * (ema20 - previous_ema20) / PIP_SIZE, 3),
            "directional_30m_return_pips": round(direction * (closes[-1] - closes[-7]) / PIP_SIZE, 3),
            "directional_60m_return_pips": round(direction * (closes[-1] - closes[-13]) / PIP_SIZE, 3),
            "prior_m5_range_pips": round((history[-1]["high"] - history[-1]["low"]) / PIP_SIZE, 3),
            "matched_entry": bool(entry),
            "match_distance_seconds": round(distance, 3) if entry else None,
            "source_row": source_row,
            "source_confidence": entry.get("confidence", ""),
            "source_profit_usd": outcomes.get(source_row) if source_row is not None else None,
        }
        labeled.append(output)

    matched = [row for row in labeled if row["matched_entry"]]
    unmatched = [row for row in labeled if not row["matched_entry"]]
    months: dict[str, object] = {}
    for month in sorted({str(row["month"]) for row in labeled}):
        rows = [row for row in labeled if row["month"] == month]
        count = sum(bool(row["matched_entry"]) for row in rows)
        months[month] = {"signals": len(rows), "matched": count, "precision_pct": pct(count, len(rows))}

    thresholds: dict[str, object] = {}
    for threshold in (800, 900, 1000, 1200, 1500, 2000):
        rows = [row for row in labeled if float(row["context_move_pips"]) >= threshold]
        count = sum(bool(row["matched_entry"]) for row in rows)
        thresholds[f"context_gte_{threshold}"] = {
            "signals": len(rows), "matched": count,
            "precision_pct": pct(count, len(rows)),
            "matched_recall_pct": pct(count, len(matched)),
        }
    for maximum in (25, 50, 100, 200):
        rows = [row for row in labeled if float(row["pivot_extension_pips"]) <= maximum]
        count = sum(bool(row["matched_entry"]) for row in rows)
        thresholds[f"extension_lte_{maximum}"] = {
            "signals": len(rows), "matched": count,
            "precision_pct": pct(count, len(rows)),
            "matched_recall_pct": pct(count, len(matched)),
        }

    summary = {
        "method": "One-to-one same-side nearest matching using only high/medium reconstructed entries.",
        "coverage_start_utc": coverage_start.isoformat(),
        "coverage_end_utc": coverage_end.isoformat(),
        "match_tolerance_seconds": args.tolerance_seconds,
        "signals_in_coverage": len(labeled),
        "matched_signals": len(matched),
        "unmatched_signals": len(unmatched),
        "baseline_precision_pct": pct(len(matched), len(labeled)),
        "matched_entry_coverage_pct": pct(len(matched), len(entries)),
        "matched_source_win_rate_pct": pct(
            sum(float(row["source_profit_usd"] or 0) > 0 for row in matched),
            sum(float(row["source_profit_usd"] or 0) != 0 for row in matched),
        ),
        "feature_medians": {
            "matched_context_move_pips": median(matched, "context_move_pips"),
            "unmatched_context_move_pips": median(unmatched, "context_move_pips"),
            "matched_pivot_extension_pips": median(matched, "pivot_extension_pips"),
            "unmatched_pivot_extension_pips": median(unmatched, "pivot_extension_pips"),
        },
        "by_month": months,
        "single_feature_sensitivity": thresholds,
        "causal_feature_discrimination": {
            field: {
                **auc(labeled, field),
                "matched_median": median(matched, field),
                "unmatched_median": median(unmatched, field),
            }
            for field in (
                "context_move_pips", "pivot_extension_pips", "atr14_pips",
                "directional_ema20_gap_pips", "directional_ema20_slope_pips",
                "directional_30m_return_pips", "directional_60m_return_pips",
                "prior_m5_range_pips",
            )
        },
        "limitations": [
            "Unmatched signals are not proven losing trades; they are only absent from the published history.",
            "Coverage starts and ends inside partial trading days.",
            "Threshold tables are descriptive and must not be promoted without walk-forward replay.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(labeled[0]))
        writer.writeheader()
        writer.writerows(labeled)
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
