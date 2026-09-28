"""Build the provisional V5 chart replay from the frozen V3 tick replay.

V5 preserves V3's causal V1/V2 selector and removes only V1 trades inside the
transition range when the frozen V4 calendar gate rejects their timestamp or
direction.  Entries and exits are therefore the same tick-replayed fills as
V3 for every retained trade.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from app.backtest import _risk_diagnostics, _validation_folds
from app.results_store import build_results_snapshot
from app.schemas import HistoricalReplayResponse, TradeResult


ROOT = Path(__file__).resolve().parents[1]
CALENDAR_FLOOR = 4.5
EXPANSION_THRESHOLD = 6.0


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _calendar_allows(timestamp: datetime, side: str) -> bool:
    schedule = {
        0: (4, 14, "buy"), 1: (3, 10, "buy"), 2: (3, 19, "buy"),
        3: (3, 12, None), 4: (3, 12, "sell"),
    }
    start, end, direction = schedule.get(timestamp.weekday(), (0, 0, None))
    return start <= timestamp.hour < end and (direction is None or side == direction)


def main() -> None:
    source_path = ROOT / "data/backtests/core-zigzag-v3-365.json"
    source = HistoricalReplayResponse.model_validate_json(source_path.read_text(encoding="utf-8"))
    context: dict[tuple[datetime, str], tuple[str, float]] = {}
    with (ROOT / "data/research/tick-backtests/zigzag_scalper_v3_adaptive.trades.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            context[(_timestamp(row["opened_at_utc"]), row["side"])] = (row["mode"], float(row["average_m5_range_60"]))

    kept: list[TradeResult] = []
    for trade in source.trades:
        mode, average_range = context.get((trade.opened_at_utc, trade.side.value), ("v1_normal_volatility", 0.0))
        transition = mode == "v1_normal_volatility" and CALENDAR_FLOOR <= average_range < EXPANSION_THRESHOLD
        if not transition or _calendar_allows(trade.opened_at_utc, trade.side.value):
            kept.append(trade.model_copy(update={
                "trade_id": trade.trade_id.replace("core-zigzag-v3", "core-zigzag-v5"),
                "setup": f"{trade.setup}; v5_mode={'v1_transition_calendar_gate' if transition else mode}",
                "note": f"{trade.note} V5: {'gate V4 aplicado' if transition else 'gate V4 não ativo'}.",
            }))

    snapshot = build_results_snapshot([trade.model_dump(mode="json") for trade in kept], "v5-derived-frozen-v3-tick-replay")
    expectancy, max_drawdown, max_loss_streak, total_costs = _risk_diagnostics(kept)
    folds = _validation_folds(kept, source.period_start_utc, source.period_end_utc, 30)
    output = source.model_copy(update={
        "bot_id": "core-zigzag-v5",
        "strategy_version": "2026-09-13-v5-v1-v2-v4-transition-gate",
        "settings_fingerprint": "v5-provisional-derived-chart-replay",
        "candidates_detected": len(kept), "candidates_eligible": len(kept),
        "candidates_blocked": max(0, len(source.trades) - len(kept)),
        "blocked_reasons": {"v5_v4_calendar_gate_block": max(0, len(source.trades) - len(kept))},
        "expectancy_r": expectancy, "max_drawdown_r": max_drawdown,
        "max_consecutive_losses": max_loss_streak, "total_costs": total_costs,
        "validation_status": "provisional_shadow", "validation_reason": "derived V5 chart replay; requires independent walk-forward with Fusion ticks",
        "validation_folds": folds, "summary": snapshot.summary, "daily_pnl": snapshot.daily_pnl,
        "trades": kept,
        "assumptions": source.assumptions + ["V5 removes only V1 transition-range trades rejected by the frozen V4 calendar gate."],
    })
    target = ROOT / "data/backtests/core-zigzag-v5-365.json"
    target.write_text(output.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"{target}: {len(kept)} retained trades; {len(source.trades) - len(kept)} blocked by V4 transition gate")


if __name__ == "__main__":
    main()
