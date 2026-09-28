"""Build the provisional V7 replay from the frozen V4.0 candidate fills."""
from datetime import timezone
from pathlib import Path

from app.backtest import _risk_diagnostics, _validation_folds
from app.results_store import build_results_snapshot
from app.schemas import HistoricalReplayResponse
from app.strategy import _zigzag_v4_calendar_allows

ROOT = Path(__file__).resolve().parents[1]


def week_of_month(timestamp):
    return min(5, (timestamp.day - 1) // 7 + 1)


def cycle_allows(timestamp, side):
    week = week_of_month(timestamp)
    return ((timestamp.weekday() == 0 and week == 2) or (timestamp.weekday() == 1 and week == 3 and side == "buy") or (timestamp.weekday() == 4 and week == 4))


def main():
    source = HistoricalReplayResponse.model_validate_json((ROOT / "data/backtests/core-zigzag-v10-365.json").read_text())
    kept = []
    blocked = {"v70_day_hour_direction_filter": 0, "v70_accuracy_cycle_filter": 0}
    for trade in source.trades:
        timestamp = trade.opened_at_utc.astimezone(timezone.utc)
        side = trade.side.value
        allowed_day, _ = _zigzag_v4_calendar_allows(timestamp, side)
        if not allowed_day:
            blocked["v70_day_hour_direction_filter"] += 1
            continue
        if not cycle_allows(timestamp, side):
            blocked["v70_accuracy_cycle_filter"] += 1
            continue
        kept.append(trade.model_copy(update={"trade_id": trade.trade_id.replace("core-zigzag-v10", "core-zigzag-v11"), "setup": f"{trade.setup}; v70_temporal_orchestration"}))
    summary = build_results_snapshot([trade.model_dump(mode="json") for trade in kept], "v70-derived-v4-temporal-orchestration").summary
    expectancy, drawdown, streak, costs = _risk_diagnostics(kept)
    output = source.model_copy(update={"bot_id": "core-zigzag-v11", "strategy_version": "2026-09-15-v70-v4-temporal-orchestration", "settings_fingerprint": "v70-provisional-derived-v4-temporal", "candidates_detected": len(source.trades), "candidates_eligible": len(kept), "candidates_blocked": sum(blocked.values()), "blocked_reasons": blocked, "expectancy_r": expectancy, "max_drawdown_r": drawdown, "max_consecutive_losses": streak, "total_costs": costs, "validation_status": "provisional_shadow", "validation_reason": "V7.0 applies temporal gates to frozen V4.0 candidates; unified causal replay is required.", "validation_folds": _validation_folds(kept, source.period_start_utc, source.period_end_utc, 30), "summary": summary, "daily_pnl": build_results_snapshot([trade.model_dump(mode="json") for trade in kept], "v70").daily_pnl, "trades": kept, "assumptions": source.assumptions + ["V7.0 is derived from frozen V4.0 fills and is not a unified causal execution replay."]})
    target = ROOT / "data/backtests/core-zigzag-v11-365.json"
    target.write_text(output.model_dump_json(indent=2) + "\n")
    print(f"{target}: {len(kept)} retained trades; {sum(blocked.values())} blocked")


if __name__ == "__main__":
    main()
