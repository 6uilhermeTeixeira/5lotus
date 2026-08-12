from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import statistics
from array import array
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


TIMEZONES = {
    "utc": UTC,
    "europe_berlin": ZoneInfo("Europe/Berlin"),
    "europe_helsinki": ZoneInfo("Europe/Helsinki"),
    "fixed_utc_plus_1": timezone(timedelta(hours=1)),
    "fixed_utc_plus_2": timezone(timedelta(hours=2)),
    "fixed_utc_plus_3": timezone(timedelta(hours=3)),
}


@dataclass
class Candidate:
    source_row: int
    hypothesis: str
    action: str
    open_price: float
    local_time: str
    utc_start_msc: int
    utc_end_msc: int
    utc_date: str
    matched_tick_msc: int | None = None
    matched_price: float | None = None
    absolute_error: float | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Correlate Myfxbook entries with Dukascopy ticks.")
    parser.add_argument("--trades", type=Path, required=True)
    parser.add_argument("--ticks", type=Path, required=True)
    parser.add_argument("--matches", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    return parser.parse_args()


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def load_candidates(path: Path) -> list[Candidate]:
    candidates: list[Candidate] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for trade in csv.DictReader(handle):
            local = datetime.fromisoformat(trade["open_time_local"])
            for name, tz in TIMEZONES.items():
                utc = local.replace(tzinfo=tz).astimezone(UTC)
                start_msc = int(utc.timestamp() * 1000)
                candidates.append(
                    Candidate(
                        source_row=int(trade["source_row"]),
                        hypothesis=name,
                        action=trade["action"],
                        open_price=float(trade["open_price"]),
                        local_time=trade["open_time_local"],
                        utc_start_msc=start_msc,
                        utc_end_msc=start_msc + 60_000,
                        utc_date=utc.date().isoformat(),
                    )
                )
    return candidates


def completed_tick_files(root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for marker in root.glob("xauusd-tick-*.csv.complete"):
        csv_path = marker.with_suffix("")
        parts = csv_path.stem.split("-")
        if len(parts) >= 7:
            result["-".join(parts[2:5])] = csv_path
    return result


def load_tick_day(path: Path) -> tuple[array, array, array]:
    timestamps = array("q")
    asks = array("d")
    bids = array("d")
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            timestamps.append(int(row["timestamp"]))
            asks.append(float(row["askPrice"]))
            bids.append(float(row["bidPrice"]))
    return timestamps, asks, bids


def match_candidates(candidates: list[Candidate], tick_files: dict[str, Path]) -> None:
    by_date: dict[str, list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        by_date[candidate.utc_date].append(candidate)

    for utc_date, daily_candidates in sorted(by_date.items()):
        tick_path = tick_files.get(utc_date)
        if tick_path is None or tick_path.stat().st_size == 0:
            continue
        timestamps, asks, bids = load_tick_day(tick_path)
        for candidate in daily_candidates:
            left = bisect.bisect_left(timestamps, candidate.utc_start_msc)
            right = bisect.bisect_left(timestamps, candidate.utc_end_msc)
            if left >= right:
                continue
            prices = asks if candidate.action == "buy" else bids
            best = min(range(left, right), key=lambda index: abs(prices[index] - candidate.open_price))
            candidate.matched_tick_msc = timestamps[best]
            candidate.matched_price = prices[best]
            candidate.absolute_error = abs(prices[best] - candidate.open_price)


def write_outputs(candidates: list[Candidate], matches_path: Path, summary_path: Path) -> None:
    matches_path.parent.mkdir(parents=True, exist_ok=True)
    with matches_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "source_row", "hypothesis", "action", "open_price", "open_time_local",
            "minute_start_utc", "matched_tick_utc", "matched_price", "absolute_error",
            "tick_offset_milliseconds",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in candidates:
            writer.writerow(
                {
                    "source_row": item.source_row,
                    "hypothesis": item.hypothesis,
                    "action": item.action,
                    "open_price": f"{item.open_price:.5f}",
                    "open_time_local": item.local_time,
                    "minute_start_utc": datetime.fromtimestamp(item.utc_start_msc / 1000, UTC).isoformat(),
                    "matched_tick_utc": (
                        datetime.fromtimestamp(item.matched_tick_msc / 1000, UTC).isoformat()
                        if item.matched_tick_msc is not None else ""
                    ),
                    "matched_price": f"{item.matched_price:.5f}" if item.matched_price is not None else "",
                    "absolute_error": f"{item.absolute_error:.5f}" if item.absolute_error is not None else "",
                    "tick_offset_milliseconds": (
                        item.matched_tick_msc - item.utc_start_msc
                        if item.matched_tick_msc is not None else ""
                    ),
                }
            )

    grouped: dict[str, list[Candidate]] = defaultdict(list)
    for item in candidates:
        grouped[item.hypothesis].append(item)
    summaries = []
    for hypothesis, items in grouped.items():
        errors = [item.absolute_error for item in items if item.absolute_error is not None]
        summaries.append(
            {
                "hypothesis": hypothesis,
                "candidate_trades": len(items),
                "matched_trades": len(errors),
                "coverage_percent": round(100 * len(errors) / len(items), 3),
                "median_absolute_error": round(statistics.median(errors), 5) if errors else None,
                "p90_absolute_error": round(percentile(errors, 0.9), 5) if errors else None,
                "mean_absolute_error": round(statistics.fmean(errors), 5) if errors else None,
                "within_0_25": sum(error <= 0.25 for error in errors),
                "within_0_50": sum(error <= 0.50 for error in errors),
                "within_1_00": sum(error <= 1.00 for error in errors),
            }
        )
    summaries.sort(key=lambda item: (item["median_absolute_error"] is None, item["median_absolute_error"] or 0))
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(
            {
                "method": "Best side-correct Dukascopy quote inside each published Myfxbook minute",
                "limitations": [
                    "Myfxbook timestamps have minute precision and unknown timezone.",
                    "Dukascopy is not the unknown broker used by the strategy.",
                    "Only dates with completed local tick files are included in matched_trades.",
                ],
                "ranking": summaries,
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    candidates = load_candidates(args.trades)
    match_candidates(candidates, completed_tick_files(args.ticks))
    write_outputs(candidates, args.matches, args.summary)
    print(args.summary.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
