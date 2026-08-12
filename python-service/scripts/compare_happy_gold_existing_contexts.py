from __future__ import annotations

import argparse
import bisect
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from app.schemas import AccountSnapshot, CandleSnapshot, DecisionRequest
from app.strategy import (
    _happy_gold_zigzag_setup,
    _multitimeframe_trend_pullback_setup,
    _stochastic_pullback_setup,
)


POINT_SIZE = 0.01
CONFIDENCES = {"high", "medium"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare reconstructed Happy Gold entries with existing strategy contexts."
    )
    parser.add_argument("--reconstructed", type=Path, required=True)
    parser.add_argument("--forward", type=Path, required=True)
    parser.add_argument("--controls", type=Path, required=True)
    parser.add_argument("--ticks", type=Path, required=True)
    parser.add_argument("--candle-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    return parser.parse_args()


def tick_files(root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for marker in root.glob("xauusd-tick-*.csv.complete"):
        path = marker.with_suffix("")
        result["-".join(path.stem.split("-")[2:5])] = path
    return result


def build_candle_cache(files: dict[str, Path], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target)
        writer.writerow(("timestamp_utc", "open", "high", "low", "close", "volume"))
        for _, path in sorted(files.items()):
            bucket_msc: int | None = None
            open_price = high = low = close = 0.0
            volume = 0
            with path.open(encoding="utf-8", newline="") as source:
                for row in csv.DictReader(source):
                    timestamp_msc = int(row["timestamp"])
                    current_bucket = timestamp_msc // 300_000 * 300_000
                    price = (float(row["askPrice"]) + float(row["bidPrice"])) / 2
                    if bucket_msc is not None and current_bucket != bucket_msc:
                        writer.writerow((
                            datetime.fromtimestamp(bucket_msc / 1000, timezone.utc).isoformat(),
                            open_price, high, low, close, volume,
                        ))
                        volume = 0
                    if current_bucket != bucket_msc:
                        bucket_msc = current_bucket
                        open_price = high = low = price
                    high = max(high, price)
                    low = min(low, price)
                    close = price
                    volume += 1
            if bucket_msc is not None:
                writer.writerow((
                    datetime.fromtimestamp(bucket_msc / 1000, timezone.utc).isoformat(),
                    open_price, high, low, close, volume,
                ))


def load_candles(path: Path) -> tuple[list[datetime], list[CandleSnapshot]]:
    timestamps: list[datetime] = []
    candles: list[CandleSnapshot] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            timestamp = datetime.fromisoformat(row["timestamp_utc"])
            timestamps.append(timestamp)
            candles.append(CandleSnapshot(
                timestamp_utc=timestamp,
                open=float(row["open"]), high=float(row["high"]),
                low=float(row["low"]), close=float(row["close"]),
                volume=float(row["volume"]),
            ))
    return timestamps, candles


def load_day_ticks(path: Path) -> tuple[list[int], list[float], list[float]]:
    timestamps: list[int] = []
    asks: list[float] = []
    bids: list[float] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            timestamps.append(int(row["timestamp"]))
            asks.append(float(row["askPrice"]))
            bids.append(float(row["bidPrice"]))
    return timestamps, asks, bids


def current_candle(
    sample: datetime, timestamps: list[int], asks: list[float], bids: list[float]
) -> tuple[CandleSnapshot, float, float] | None:
    sample_msc = int(sample.timestamp() * 1000)
    right = bisect.bisect_right(timestamps, sample_msc)
    if right == 0:
        return None
    bucket_msc = sample_msc // 300_000 * 300_000
    left = bisect.bisect_left(timestamps, bucket_msc)
    if left >= right:
        return None
    mids = [(asks[index] + bids[index]) / 2 for index in range(left, right)]
    return (
        CandleSnapshot(
            timestamp_utc=datetime.fromtimestamp(bucket_msc / 1000, timezone.utc),
            open=mids[0], high=max(mids), low=min(mids), close=mids[-1], volume=len(mids),
        ),
        bids[right - 1],
        asks[right - 1],
    )


def request_for(
    sample: datetime,
    complete_timestamps: list[datetime],
    complete_candles: list[CandleSnapshot],
    partial: CandleSnapshot,
    bid: float,
    ask: float,
) -> DecisionRequest:
    index = bisect.bisect_left(complete_timestamps, partial.timestamp_utc)
    candles = complete_candles[max(0, index - 1000):index] + [partial]
    return DecisionRequest(
        request_id=f"research-{int(sample.timestamp() * 1000)}",
        timestamp_utc=sample,
        symbol="XAUUSD", timeframe="M5", bid=bid, ask=ask,
        spread_points=(ask - bid) / POINT_SIZE, point_size=POINT_SIZE,
        value_per_point_per_lot=0.1, candles=candles, positions=[],
        account=AccountSnapshot(balance=10_000, equity=10_000, margin_free=10_000),
    )


def label(setup: object | None, action: str) -> tuple[bool, bool, str]:
    if setup is None:
        return False, False, ""
    setup_action = setup.action.value  # type: ignore[union-attr]
    return True, setup_action == action, setup_action


def rates(rows: list[dict[str, object]], prefix: str) -> dict[str, float | int | None]:
    count = len(rows)
    candidates = sum(bool(row[f"{prefix}_candidate"]) for row in rows)
    matches = sum(bool(row[f"{prefix}_direction_match"]) for row in rows)
    return {
        "samples": count,
        "candidate_count": candidates,
        "candidate_pct": round(100 * candidates / count, 3) if count else None,
        "direction_match_count": matches,
        "direction_match_pct": round(100 * matches / count, 3) if count else None,
    }


def main() -> None:
    args = parse_args()
    files = tick_files(args.ticks)
    if not args.candle_cache.exists():
        build_candle_cache(files, args.candle_cache)
    complete_timestamps, complete_candles = load_candles(args.candle_cache)

    outcomes: dict[int, float] = {}
    with args.forward.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            outcomes[int(row["source_row"])] = float(row["profit_usd"])

    samples: list[dict[str, object]] = []
    with args.reconstructed.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["confidence"] in CONFIDENCES:
                source_row = int(row["source_row"])
                samples.append({
                    "sample_type": "entry", "source_row": source_row,
                    "confidence": row["confidence"], "action": row["action"],
                    "sample_time_utc": row["entry_time_utc"],
                    "profit_usd": outcomes.get(source_row),
                })
    feature_rows: dict[tuple[str, int, str], dict[str, str]] = {}
    with args.controls.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            feature_rows[(row["sample_type"], int(row["source_row"]), row["sample_time_utc"])] = row
            if row["sample_type"] == "control":
                samples.append({
                    "sample_type": "control", "source_row": int(row["source_row"]),
                    "confidence": row["confidence"], "action": row["action"],
                    "sample_time_utc": row["sample_time_utc"], "profit_usd": None,
                })

    by_date: dict[str, list[dict[str, object]]] = defaultdict(list)
    for sample in samples:
        by_date[str(sample["sample_time_utc"])[:10]].append(sample)

    results: list[dict[str, object]] = []
    for date, date_samples in sorted(by_date.items()):
        path = files.get(date)
        if path is None:
            continue
        tick_timestamps, asks, bids = load_day_ticks(path)
        for sample_row in date_samples:
            sample_time = datetime.fromisoformat(str(sample_row["sample_time_utc"]))
            current = current_candle(sample_time, tick_timestamps, asks, bids)
            if current is None:
                continue
            partial, bid, ask = current
            request = request_for(
                sample_time, complete_timestamps, complete_candles, partial, bid, ask
            )
            strategies = {
                "zigzag": _happy_gold_zigzag_setup(request),
                "stochastic": _stochastic_pullback_setup(request),
                "multitimeframe": _multitimeframe_trend_pullback_setup(request),
            }
            output = dict(sample_row)
            feature = feature_rows.get((
                str(sample_row["sample_type"]),
                int(sample_row["source_row"]),
                str(sample_row["sample_time_utc"]),
            ), {})
            output["pre_60s_directional_move_pips"] = feature.get("pre_60s_directional_move_pips", "")
            output["pre_900s_directional_move_pips"] = feature.get("pre_900s_directional_move_pips", "")
            for name, setup in strategies.items():
                candidate, match, setup_action = label(setup, str(sample_row["action"]))
                output[f"{name}_candidate"] = candidate
                output[f"{name}_direction_match"] = match
                output[f"{name}_action"] = setup_action
            output["any_direction_match"] = any(
                bool(output[f"{name}_direction_match"]) for name in strategies
            )
            results.append(output)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)

    entries = [row for row in results if row["sample_type"] == "entry"]
    controls = [row for row in results if row["sample_type"] == "control"]
    wins = [row for row in entries if float(row["profit_usd"] or 0) > 0]
    losses = [row for row in entries if float(row["profit_usd"] or 0) < 0]
    summary: dict[str, object] = {
        "method": "Existing strategies evaluated at reconstructed entry and paired control timestamps using causal Dukascopy M5 candles.",
        "entries": len(entries), "controls": len(controls), "wins": len(wins), "losses": len(losses),
        "strategies": {},
        "limitations": [
            "Dukascopy mid-price candles proxy the unknown original broker feed.",
            "Reconstructed timestamps are limited to high/medium-confidence 2025 trades.",
            "A direction match is contextual evidence, not proof that the original bot used that indicator.",
        ],
    }
    strategy_summary = summary["strategies"]
    assert isinstance(strategy_summary, dict)
    for name in ("zigzag", "stochastic", "multitimeframe"):
        strategy_summary[name] = {
            "entries": rates(entries, name), "controls": rates(controls, name),
            "wins": rates(wins, name), "losses": rates(losses, name),
        }
    summary["any_direction_match"] = {
        "entries": sum(bool(row["any_direction_match"]) for row in entries),
        "controls": sum(bool(row["any_direction_match"]) for row in controls),
    }
    hybrids: dict[str, object] = {}
    for seconds, thresholds in ((60, (160, 300)), (900, (500, 800, 1000))):
        field = f"pre_{seconds}s_directional_move_pips"
        for threshold in thresholds:
            key = f"zigzag_and_{seconds}s_move_gte_{threshold}"
            selected_entries = [
                row for row in entries
                if bool(row["zigzag_direction_match"])
                and row[field] != "" and float(row[field]) >= threshold
            ]
            selected_controls = [
                row for row in controls
                if bool(row["zigzag_direction_match"])
                and row[field] != "" and float(row[field]) >= threshold
            ]
            wins_count = sum(float(row["profit_usd"] or 0) > 0 for row in selected_entries)
            losses_count = sum(float(row["profit_usd"] or 0) < 0 for row in selected_entries)
            hybrids[key] = {
                "entries": len(selected_entries), "controls": len(selected_controls),
                "wins": wins_count, "losses": losses_count,
                "win_rate_pct_excluding_breakeven": (
                    round(100 * wins_count / (wins_count + losses_count), 3)
                    if wins_count + losses_count else None
                ),
            }
    summary["hybrid_hypotheses"] = hybrids
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
