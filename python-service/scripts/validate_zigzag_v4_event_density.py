"""Validate a frozen V4 entry rule against every one-second market observation."""

from __future__ import annotations

import bisect
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import numpy as np

from app.config import get_settings
from app.local_dataset import DatasetRelease


ROOT = Path(__file__).resolve().parents[1]
PIP_SIZE = 0.01
MINIMUM_60S_MOVE_PIPS = 47.0
MINIMUM_900S_MOVE_PIPS = 190.0
STOP_PIPS = 240.0
TARGET_PIPS = 1000.0
MAX_HOLD_SECONDS = 60
COOLDOWN_SECONDS = 180
LOT = 0.20
ROUND_TURN_COMMISSION = 0.90


def metrics(rows: list[dict[str, object]]) -> dict[str, object]:
    pnl = [float(row["net_pnl"]) for row in rows]
    gross_profit = sum(value for value in pnl if value > 0)
    gross_loss = -sum(value for value in pnl if value < 0)
    return {
        "trades": len(rows),
        "win_rate_pct": round(100 * sum(value > 0 for value in pnl) / len(pnl), 2) if pnl else None,
        "net_pnl": round(sum(pnl), 2),
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else None,
        "exits": {reason: sum(row["exit_reason"] == reason for row in rows) for reason in ("stop", "target", "time_60s")},
    }


def partition(rows: list[dict[str, object]], start: str, end: str) -> list[dict[str, object]]:
    return [row for row in rows if start <= str(row["opened_at_utc"])[:10] <= end]


def load_reference_signals(path: Path) -> dict[str, list[int]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    signals = {"buy": [], "sell": []}
    for trade in payload["trades"]:
        opened = datetime.fromisoformat(str(trade["opened_at_utc"]).replace("Z", "+00:00"))
        signals[str(trade["side"])].append(int(opened.timestamp() * 1000))
    for timestamps in signals.values():
        timestamps.sort()
    return signals


def follows_signal(timestamp: int, side: str, signals: dict[str, list[int]], window_seconds: int) -> bool:
    timestamps = signals[side]
    index = bisect.bisect_right(timestamps, timestamp) - 1
    return index >= 0 and timestamp - timestamps[index] <= window_seconds * 1000


def search_financial_filters(
    trades: list[dict[str, object]], pnl_key: str = "net_pnl"
) -> dict[str, object]:
    timestamps = np.array([str(row["opened_at_utc"]) for row in trades])
    pnl = np.array([float(row[pnl_key]) for row in trades])
    training = (timestamps >= "2025-10-15") & (timestamps <= "2025-12-31T23:59:59")
    predicates: list[tuple[str, np.ndarray]] = []
    numeric_features = (
        "move_5s_pips", "move_10s_pips", "move_30s_pips", "move_60s_pips",
        "move_300s_pips", "move_900s_pips", "spread_pips", "acceleration_60s_vs_300s",
    )
    for feature in numeric_features:
        values = np.array([float(row[feature]) for row in trades])
        training_values = values[training]
        for quantile in (.1, .2, .3, .4, .5, .6, .7, .8, .9):
            threshold = float(np.quantile(training_values, quantile))
            predicates.append((f"{feature}>={threshold:.6g}", values >= threshold))
            predicates.append((f"{feature}<={threshold:.6g}", values <= threshold))
    sides = np.array([str(row["side"]) for row in trades])
    hours = np.array([datetime.fromisoformat(value).hour for value in timestamps])
    weekdays = np.array([datetime.fromisoformat(value).weekday() for value in timestamps])
    predicates.extend((
        ("side=buy", sides == "buy"), ("side=sell", sides == "sell"),
        ("weekday!=friday", weekdays != 4),
    ))
    for hour in range(5, 18):
        predicates.append((f"hour<{hour}", hours < hour))
        predicates.append((f"hour>={hour}", hours >= hour))

    def score(mask: np.ndarray) -> dict[str, float | int | None]:
        values = pnl[mask]
        gross_profit = float(values[values > 0].sum())
        gross_loss = float(-values[values < 0].sum())
        return {
            "trades": int(len(values)),
            "net_pnl": round(float(values.sum()), 2),
            "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else None,
            "win_rate_pct": round(100 * float((values > 0).mean()), 2) if len(values) else None,
        }

    singles = []
    for name, mask in predicates:
        training_metrics = score(mask & training)
        if int(training_metrics["trades"]) >= 100:
            singles.append((float(training_metrics["profit_factor"] or 0), name, mask, training_metrics))
    seeds = sorted(singles, reverse=True)[:40]
    candidates = [(value, [name], mask, result) for value, name, mask, result in singles]
    for left_index, (_, left_name, left_mask, _) in enumerate(seeds):
        for _, right_name, right_mask, _ in seeds[left_index + 1:]:
            mask = left_mask & right_mask
            training_metrics = score(mask & training)
            if int(training_metrics["trades"]) >= 50:
                candidates.append((
                    float(training_metrics["profit_factor"] or 0),
                    [left_name, right_name], mask, training_metrics,
                ))
    ranked = sorted(candidates, key=lambda item: (item[0], float(item[3]["net_pnl"])), reverse=True)
    periods = {
        "training_2025_oct_dec": training,
        "holdout_2026_full": (timestamps >= "2026-01-01") & (timestamps <= "2026-09-01T23:59:59"),
        "holdout_2026_jan_apr": (timestamps >= "2026-01-01") & (timestamps <= "2026-04-30T23:59:59"),
        "holdout_2026_may_sep": (timestamps >= "2026-05-01") & (timestamps <= "2026-09-01T23:59:59"),
    }
    output = []
    for _, rules, mask, training_metrics in ranked[:20]:
        output.append({
            "rules": rules,
            **{name: training_metrics if name == "training_2025_oct_dec" else score(mask & period) for name, period in periods.items()},
        })
    robust = [
        row for row in output
        if float(row["training_2025_oct_dec"]["profit_factor"] or 0) > 1
        and float(row["holdout_2026_jan_apr"]["profit_factor"] or 0) > 1
        and float(row["holdout_2026_may_sep"]["profit_factor"] or 0) > 1
    ]
    return {
        "pnl_source": pnl_key,
        "selection": "single filters and pairs ranked only by 2025 training profit factor",
        "minimum_training_trades": {"single": 100, "pair": 50},
        "top_20_training_rules": output,
        "robust_rules": robust,
        "decision": "candidate_found" if robust else "rejected_no_rule_profitable_in_both_2026_holdouts",
    }


def main() -> None:
    release = DatasetRelease.open(get_settings().lotus_data_root, "CURRENT")
    zigzag_v1 = load_reference_signals(ROOT / "data/backtests-operational/core-zigzag-365.json")
    stochastic_v3 = load_reference_signals(ROOT / "data/backtests-operational/core-stochastic-v3-365.json")
    manifest = [
        row for row in release.manifest["aggregations"]["1s"]
        if "2025-10-15" <= row["day"] <= "2026-09-01"
    ]
    trades: list[dict[str, object]] = []
    countertrend_trades: list[dict[str, object]] = []
    modeled_spread_trades: dict[int, list[dict[str, object]]] = {0: [], 10: []}
    connection = duckdb.connect(":memory:")
    try:
        for manifest_row in manifest:
            values = connection.execute(
                "SELECT t,c,spread_mean FROM read_parquet(?) ORDER BY t",
                [[str(release.root / manifest_row["path"])]],
            ).fetchnumpy()
            timestamps = values["t"].astype(np.int64)
            mid = values["c"].astype(float)
            spread = values["spread_mean"].astype(float)
            if len(timestamps) < 2:
                continue
            indexes = np.arange(len(timestamps))
            windows = (5, 10, 30, 60, 300, 900)
            window_indexes = {seconds: np.searchsorted(timestamps, timestamps - seconds * 1000) for seconds in windows}
            index_60s = window_indexes[60]
            index_900s = window_indexes[900]
            valid = index_900s < indexes
            hours = (timestamps // 3_600_000) % 24
            valid &= (hours >= 3) & (hours < 19)
            move_60s = (mid - mid[index_60s]) / PIP_SIZE
            move_900s = (mid - mid[index_900s]) / PIP_SIZE
            qualified = {
                1: valid & (move_60s >= MINIMUM_60S_MOVE_PIPS) & (move_900s >= MINIMUM_900S_MOVE_PIPS),
                -1: valid & (move_60s <= -MINIMUM_60S_MOVE_PIPS) & (move_900s <= -MINIMUM_900S_MOVE_PIPS),
            }
            armed = {1: True, -1: True}
            blocked_until = 0
            for index, timestamp in enumerate(timestamps):
                for direction in (1, -1):
                    if not qualified[direction][index]:
                        armed[direction] = True
                if timestamp < blocked_until:
                    continue
                directions = [direction for direction in (1, -1) if qualified[direction][index] and armed[direction]]
                if not directions:
                    continue
                direction = directions[0]
                armed[direction] = False
                entry = mid[index] + direction * spread[index] / 2
                stop = entry - direction * STOP_PIPS * PIP_SIZE
                target = entry + direction * TARGET_PIPS * PIP_SIZE
                end = int(np.searchsorted(timestamps, timestamp + MAX_HOLD_SECONDS * 1000, side="right"))
                executable = mid[index:end] - direction * spread[index:end] / 2
                stop_hits = np.flatnonzero(direction * (executable - stop) <= 0)
                target_hits = np.flatnonzero(direction * (executable - target) >= 0)
                last_offset = end - index - 1
                stop_offset = int(stop_hits[0]) if len(stop_hits) else last_offset
                target_offset = int(target_hits[0]) if len(target_hits) else last_offset
                offset = min(stop_offset, target_offset)
                exit_index = index + offset
                exit_reason = "stop" if stop_offset < target_offset else "target" if target_offset < stop_offset else "time_60s"
                exit_price = mid[exit_index] - direction * spread[exit_index] / 2
                pnl_pips = direction * (exit_price - entry) / PIP_SIZE
                aligned_moves = {
                    seconds: direction * (mid[index] - mid[window_indexes[seconds][index]]) / PIP_SIZE
                    for seconds in windows
                }
                trades.append({
                    "opened_at_utc": datetime.fromtimestamp(timestamp / 1000, UTC).isoformat(),
                    "side": "buy" if direction == 1 else "sell",
                    "exit_reason": exit_reason,
                    "net_pnl": round(pnl_pips * LOT - ROUND_TURN_COMMISSION, 2),
                    "timestamp_msc": int(timestamp),
                    **{f"move_{seconds}s_pips": round(value, 3) for seconds, value in aligned_moves.items()},
                    "spread_pips": round(spread[index] / PIP_SIZE, 3),
                    "acceleration_60s_vs_300s": round(
                        aligned_moves[60] / max(abs(aligned_moves[300]), 1.0), 6
                    ),
                })
                counter_direction = -direction
                counter_entry = mid[index] + counter_direction * spread[index] / 2
                counter_stop = counter_entry - counter_direction * STOP_PIPS * PIP_SIZE
                counter_target = counter_entry + counter_direction * TARGET_PIPS * PIP_SIZE
                counter_executable = mid[index:end] - counter_direction * spread[index:end] / 2
                counter_stop_hits = np.flatnonzero(counter_direction * (counter_executable - counter_stop) <= 0)
                counter_target_hits = np.flatnonzero(counter_direction * (counter_executable - counter_target) >= 0)
                counter_stop_offset = int(counter_stop_hits[0]) if len(counter_stop_hits) else last_offset
                counter_target_offset = int(counter_target_hits[0]) if len(counter_target_hits) else last_offset
                counter_offset = min(counter_stop_offset, counter_target_offset)
                counter_exit_index = index + counter_offset
                counter_reason = (
                    "stop" if counter_stop_offset < counter_target_offset
                    else "target" if counter_target_offset < counter_stop_offset else "time_60s"
                )
                counter_exit = mid[counter_exit_index] - counter_direction * spread[counter_exit_index] / 2
                counter_pips = counter_direction * (counter_exit - counter_entry) / PIP_SIZE
                countertrend_trades.append({
                    "opened_at_utc": datetime.fromtimestamp(timestamp / 1000, UTC).isoformat(),
                    "side": "buy" if counter_direction == 1 else "sell",
                    "exit_reason": counter_reason,
                    "net_pnl": round(counter_pips * LOT - ROUND_TURN_COMMISSION, 2),
                })
                for modeled_spread_pips, scenario_trades in modeled_spread_trades.items():
                    half_spread = modeled_spread_pips * PIP_SIZE / 2
                    modeled_entry = mid[index] + direction * half_spread
                    modeled_stop = modeled_entry - direction * STOP_PIPS * PIP_SIZE
                    modeled_target = modeled_entry + direction * TARGET_PIPS * PIP_SIZE
                    modeled_executable = mid[index:end] - direction * half_spread
                    modeled_stop_hits = np.flatnonzero(direction * (modeled_executable - modeled_stop) <= 0)
                    modeled_target_hits = np.flatnonzero(direction * (modeled_executable - modeled_target) >= 0)
                    modeled_stop_offset = int(modeled_stop_hits[0]) if len(modeled_stop_hits) else last_offset
                    modeled_target_offset = int(modeled_target_hits[0]) if len(modeled_target_hits) else last_offset
                    modeled_offset = min(modeled_stop_offset, modeled_target_offset)
                    modeled_exit_index = index + modeled_offset
                    modeled_reason = (
                        "stop" if modeled_stop_offset < modeled_target_offset
                        else "target" if modeled_target_offset < modeled_stop_offset else "time_60s"
                    )
                    modeled_exit = mid[modeled_exit_index] - direction * half_spread
                    modeled_pips = direction * (modeled_exit - modeled_entry) / PIP_SIZE
                    scenario_trades.append({
                        "opened_at_utc": datetime.fromtimestamp(timestamp / 1000, UTC).isoformat(),
                        "side": "buy" if direction == 1 else "sell",
                        "exit_reason": modeled_reason,
                        "net_pnl": round(modeled_pips * LOT - ROUND_TURN_COMMISSION, 2),
                    })
                    if modeled_spread_pips == 0:
                        trades[-1]["net_pnl_spread_0"] = scenario_trades[-1]["net_pnl"]
                blocked_until = timestamps[exit_index] + COOLDOWN_SECONDS * 1000
    finally:
        connection.close()

    intersections: dict[str, object] = {}
    for window_seconds in (5, 30, 60, 300):
        selectors = {
            "zigzag_v1_same_side": lambda row, window=window_seconds: follows_signal(
                int(row["timestamp_msc"]), str(row["side"]), zigzag_v1, window
            ),
            "stochastic_v3_sell": lambda row, window=window_seconds: row["side"] == "sell" and follows_signal(
                int(row["timestamp_msc"]), "sell", stochastic_v3, window
            ),
        }
        selectors["v1_or_stochastic_v3"] = lambda row, window=window_seconds: (
            follows_signal(int(row["timestamp_msc"]), str(row["side"]), zigzag_v1, window)
            or row["side"] == "sell" and follows_signal(int(row["timestamp_msc"]), "sell", stochastic_v3, window)
        )
        for name, selector in selectors.items():
            selected = [row for row in trades if selector(row)]
            intersections[f"{name}_{window_seconds}s"] = {
                "training_2025_oct_dec": metrics(partition(selected, "2025-10-15", "2025-12-31")),
                "holdout_2026_jan_apr": metrics(partition(selected, "2026-01-01", "2026-04-30")),
                "holdout_2026_may_sep": metrics(partition(selected, "2026-05-01", "2026-09-01")),
                "overall": metrics(selected),
            }

    pullback_mask = [
        float(row["move_5s_pips"]) <= -17
        and float(row["acceleration_60s_vs_300s"]) <= 0.16173
        for row in trades
    ]
    pullback_cost_scenarios: dict[str, object] = {}
    for name, rows in {
        "observed_spread": trades,
        "spread_0_pips": modeled_spread_trades[0],
        "spread_10_pips": modeled_spread_trades[10],
    }.items():
        selected = [row for row, keep in zip(rows, pullback_mask, strict=True) if keep]
        pullback_cost_scenarios[name] = {
            "training_2025_oct_dec": metrics(partition(selected, "2025-10-15", "2025-12-31")),
            "holdout_2026_full": metrics(partition(selected, "2026-01-01", "2026-09-01")),
            "holdout_2026_jan_apr": metrics(partition(selected, "2026-01-01", "2026-04-30")),
            "holdout_2026_may_sep": metrics(partition(selected, "2026-05-01", "2026-09-01")),
        }

    report = {
        "method": "Rule selected on paired 2025 controls, then scanned at every 1s market observation without timestamp matching.",
        "dataset_version": release.version,
        "frozen_rule": {
            "directional_move_60s_min_pips": MINIMUM_60S_MOVE_PIPS,
            "directional_move_900s_min_pips": MINIMUM_900S_MOVE_PIPS,
            "session_utc": "03:00-19:00",
            "rearm": "qualification must become false",
            "cooldown_seconds_after_exit": COOLDOWN_SECONDS,
        },
        "execution_model": {
            "resolution": "1s", "stop_pips": STOP_PIPS, "target_pips": TARGET_PIPS,
            "max_hold_seconds": MAX_HOLD_SECONDS, "lot": LOT,
            "round_turn_commission": ROUND_TURN_COMMISSION,
        },
        "training_2025_oct_dec": metrics(partition(trades, "2025-10-15", "2025-12-31")),
        "holdout_2026_jan_apr": metrics(partition(trades, "2026-01-01", "2026-04-30")),
        "holdout_2026_may_sep": metrics(partition(trades, "2026-05-01", "2026-09-01")),
        "overall": metrics(trades),
        "countertrend_exhaustion_test": {
            "training_2025_oct_dec": metrics(partition(countertrend_trades, "2025-10-15", "2025-12-31")),
            "holdout_2026_jan_apr": metrics(partition(countertrend_trades, "2026-01-01", "2026-04-30")),
            "holdout_2026_may_sep": metrics(partition(countertrend_trades, "2026-05-01", "2026-09-01")),
            "overall": metrics(countertrend_trades),
        },
        "modeled_spread_scenarios": {
            f"spread_{spread_pips}_pips": {
                "training_2025_oct_dec": metrics(partition(rows, "2025-10-15", "2025-12-31")),
                "holdout_2026_jan_apr": metrics(partition(rows, "2026-01-01", "2026-04-30")),
                "holdout_2026_may_sep": metrics(partition(rows, "2026-05-01", "2026-09-01")),
                "overall": metrics(rows),
            }
            for spread_pips, rows in modeled_spread_trades.items()
        },
        "causal_strategy_intersections": intersections,
        "financial_filter_search": search_financial_filters(trades),
        "zero_spread_filter_search": search_financial_filters(trades, "net_pnl_spread_0"),
        "pullback_deceleration_probe": {
            "rule": "base 60s/900s momentum, move_5s <= -17 pips, acceleration_60s_vs_300s <= 0.16173",
            "cost_scenarios": pullback_cost_scenarios,
            "status": "fragile_zero_spread_only_not_promoted",
        },
        "decision": "rejected_excessive_false_positive_density_and_negative_expectancy",
        "interpretation": "Paired controls show momentum near known entries, but momentum is not a sufficiently unique entry trigger in the full market stream.",
    }
    output = ROOT / "data/research/zigzag_scalper_v4_event_density.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
