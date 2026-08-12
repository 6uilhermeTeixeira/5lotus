from __future__ import annotations

import argparse
import bisect
import csv
import json
import statistics
from array import array
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo


TIMEZONE_NAME = "Europe/Helsinki"
TIMEZONE = ZoneInfo(TIMEZONE_NAME)
DEFAULT_DURATION_TOLERANCE_MSC = 1_500


@dataclass
class Trade:
    row: dict[str, str]
    open_start_msc: int
    close_start_msc: int
    utc_date: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconstruct second-level Myfxbook fills from ticks.")
    parser.add_argument("--trades", type=Path, required=True)
    parser.add_argument("--ticks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--duration-tolerance-ms", type=int, default=DEFAULT_DURATION_TOLERANCE_MSC)
    return parser.parse_args()


def local_minute_msc(value: str) -> int:
    local = datetime.fromisoformat(value).replace(tzinfo=TIMEZONE)
    return int(local.astimezone(UTC).timestamp() * 1000)


def load_trades(path: Path) -> list[Trade]:
    result: list[Trade] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["source_timezone"] != TIMEZONE_NAME:
                raise SystemExit(f"Unexpected source_timezone in row {row['source_row']}")
            open_msc = local_minute_msc(row["open_time_local"])
            result.append(
                Trade(
                    row=row,
                    open_start_msc=open_msc,
                    close_start_msc=local_minute_msc(row["close_time_local"]),
                    utc_date=datetime.fromtimestamp(open_msc / 1000, UTC).date().isoformat(),
                )
            )
    return result


def completed_tick_files(root: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for marker in root.glob("xauusd-tick-*.csv.complete"):
        csv_path = marker.with_suffix("")
        parts = csv_path.stem.split("-")
        files["-".join(parts[2:5])] = csv_path
    return files


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


def reconstruct(
    trade: Trade,
    timestamps: array,
    asks: array,
    bids: array,
    duration_tolerance_msc: int,
) -> dict[str, object] | None:
    entry_left = bisect.bisect_left(timestamps, trade.open_start_msc)
    entry_right = bisect.bisect_left(timestamps, trade.open_start_msc + 60_000)
    if entry_left >= entry_right:
        return None

    is_buy = trade.row["action"] == "buy"
    entry_prices = asks if is_buy else bids
    exit_prices = bids if is_buy else asks
    open_price = float(trade.row["open_price"])
    close_price = float(trade.row["close_price"])
    published_duration_msc = int(trade.row["duration_seconds"]) * 1000
    close_minute_end = trade.close_start_msc + 60_000
    minimum_entry_error = min(
        abs(entry_prices[index] - open_price) for index in range(entry_left, entry_right)
    )
    fallback_entry_index = min(
        range(entry_left, entry_right),
        key=lambda index: (abs(entry_prices[index] - open_price), timestamps[index]),
    )
    best: tuple[float, int, float, int, int] | None = None

    for entry_index in range(entry_left, entry_right):
        entry_error = abs(entry_prices[entry_index] - open_price)
        if entry_error > minimum_entry_error + 0.005_001:
            continue
        expected_exit = timestamps[entry_index] + published_duration_msc
        exit_left_msc = max(trade.close_start_msc, expected_exit - duration_tolerance_msc)
        exit_right_msc = min(close_minute_end, expected_exit + duration_tolerance_msc + 1)
        exit_left = bisect.bisect_left(timestamps, exit_left_msc)
        exit_right = bisect.bisect_left(timestamps, exit_right_msc)
        if exit_left >= exit_right:
            continue
        exit_index = min(
            range(exit_left, exit_right),
            key=lambda index: (
                abs(exit_prices[index] - close_price),
                abs(timestamps[index] - expected_exit),
            ),
        )
        exit_error = abs(exit_prices[exit_index] - close_price)
        duration_error = abs((timestamps[exit_index] - timestamps[entry_index]) - published_duration_msc)
        candidate = (
            exit_error,
            duration_error,
            entry_error,
            entry_index,
            exit_index,
        )
        if best is None or candidate < best:
            best = candidate

    if best is None:
        return {
            "source_row": int(trade.row["source_row"]),
            "action": trade.row["action"],
            "open_time_local_minute": trade.row["open_time_local"],
            "close_time_local_minute": trade.row["close_time_local"],
            "source_timezone": TIMEZONE_NAME,
            "entry_time_utc": datetime.fromtimestamp(timestamps[fallback_entry_index] / 1000, UTC).isoformat(),
            "exit_time_utc": "",
            "entry_tick_price": f"{entry_prices[fallback_entry_index]:.5f}",
            "published_open_price": trade.row["open_price"],
            "entry_absolute_error": f"{minimum_entry_error:.5f}",
            "exit_tick_price": "",
            "published_close_price": trade.row["close_price"],
            "exit_absolute_error": "",
            "combined_price_error": "",
            "published_duration_seconds": int(trade.row["duration_seconds"]),
            "reconstructed_duration_milliseconds": "",
            "duration_error_milliseconds": "",
            "confidence": "entry_only",
        }
    exit_error, duration_error, entry_error, entry_index, exit_index = best
    actual_duration = timestamps[exit_index] - timestamps[entry_index]
    return {
        "source_row": int(trade.row["source_row"]),
        "action": trade.row["action"],
        "open_time_local_minute": trade.row["open_time_local"],
        "close_time_local_minute": trade.row["close_time_local"],
        "source_timezone": TIMEZONE_NAME,
        "entry_time_utc": datetime.fromtimestamp(timestamps[entry_index] / 1000, UTC).isoformat(),
        "exit_time_utc": datetime.fromtimestamp(timestamps[exit_index] / 1000, UTC).isoformat(),
        "entry_tick_price": f"{entry_prices[entry_index]:.5f}",
        "published_open_price": trade.row["open_price"],
        "entry_absolute_error": f"{entry_error:.5f}",
        "exit_tick_price": f"{exit_prices[exit_index]:.5f}",
        "published_close_price": trade.row["close_price"],
        "exit_absolute_error": f"{exit_error:.5f}",
        "combined_price_error": f"{entry_error + exit_error:.5f}",
        "published_duration_seconds": int(trade.row["duration_seconds"]),
        "reconstructed_duration_milliseconds": actual_duration,
        "duration_error_milliseconds": duration_error,
        "confidence": (
            "high" if entry_error <= 0.10 and exit_error <= 0.10 and duration_error <= 750
            else "medium" if entry_error <= 0.25 and exit_error <= 0.25
            else "low"
        ),
    }


def main() -> None:
    args = parse_args()
    trades = load_trades(args.trades)
    tick_files = completed_tick_files(args.ticks)
    by_date: dict[str, list[Trade]] = defaultdict(list)
    for trade in trades:
        by_date[trade.utc_date].append(trade)

    results: list[dict[str, object]] = []
    eligible = 0
    for utc_date, daily_trades in sorted(by_date.items()):
        tick_file = tick_files.get(utc_date)
        if tick_file is None or tick_file.stat().st_size == 0:
            continue
        eligible += len(daily_trades)
        timestamps, asks, bids = load_tick_day(tick_file)
        for trade in daily_trades:
            result = reconstruct(trade, timestamps, asks, bids, args.duration_tolerance_ms)
            if result is not None:
                results.append(result)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)

    entry_errors = [float(row["entry_absolute_error"]) for row in results]
    exit_errors = [float(row["exit_absolute_error"]) for row in results if row["exit_absolute_error"] != ""]
    confidence = defaultdict(int)
    for row in results:
        confidence[str(row["confidence"])] += 1
    summary = {
        "timezone": TIMEZONE_NAME,
        "duration_tolerance_milliseconds": args.duration_tolerance_ms,
        "total_trades": len(trades),
        "eligible_trades_with_tick_day": eligible,
        "entry_reconstructed_trades": len(results),
        "entry_exit_reconstructed_trades": len(exit_errors),
        "confidence": dict(sorted(confidence.items())),
        "median_entry_absolute_error": statistics.median(entry_errors) if entry_errors else None,
        "median_exit_absolute_error": statistics.median(exit_errors) if exit_errors else None,
        "max_entry_absolute_error": max(entry_errors, default=None),
        "max_exit_absolute_error": max(exit_errors, default=None),
    }
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
