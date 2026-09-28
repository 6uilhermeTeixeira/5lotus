"""Compose the V7.2 exploratory chart from the existing causal V3 and V7 replays."""
from datetime import timedelta
from pathlib import Path

from app.backtest import _risk_diagnostics, _validation_folds
from app.results_store import build_results_snapshot
from app.schemas import HistoricalReplayResponse

V3_RELEASE_WEEKDAYS = {2, 3}


def main():
    root = Path(__file__).resolve().parents[1]
    v3 = HistoricalReplayResponse.model_validate_json((root / "data/backtests/core-zigzag-v3-365.json").read_text())
    v7 = HistoricalReplayResponse.model_validate_json((root / "data/backtests/core-zigzag-v7-365.json").read_text())
    selected = []
    for trade in v7.trades:
        if trade.opened_at_utc.weekday() not in V3_RELEASE_WEEKDAYS:
            selected.append(trade.model_copy(update={
                "trade_id": trade.trade_id.replace("core-zigzag-v7", "core-zigzag-v72"),
                "setup": "zigzag_v72_v7_branch",
                "note": trade.note + " V7.2: ramo V7 fora de quarta/quinta UTC.",
            }))
    for trade in v3.trades:
        if trade.opened_at_utc.weekday() in V3_RELEASE_WEEKDAYS:
            selected.append(trade.model_copy(update={
                "trade_id": trade.trade_id.replace("core-zigzag-v3", "core-zigzag-v72"),
                "setup": "zigzag_v72_v3_release_branch",
                "note": trade.note + " V7.2: V3 pura na quarta/quinta UTC.",
            }))
    selected.sort(key=lambda trade: trade.opened_at_utc)
    snapshot = build_results_snapshot([trade.model_dump(mode="json") for trade in selected], "v72-exploratory-composite")
    expectancy, drawdown, streak, costs = _risk_diagnostics(selected)
    output = v7.model_copy(update={
        "bot_id": "core-zigzag-v72",
        "strategy_version": "v7.2-v3-wed-thu-1",
        "settings_fingerprint": "v72-exploratory-composite-1",
        "trades": selected,
        "summary": snapshot.summary,
        "daily_pnl": snapshot.daily_pnl,
        "expectancy_r": expectancy,
        "max_drawdown_r": drawdown,
        "max_consecutive_losses": streak,
        "total_costs": costs,
        "candidates_detected": len(v7.trades) + len(v3.trades),
        "candidates_eligible": len(selected),
        "candidates_blocked": 0,
        "blocked_reasons": {},
        "regime_counts": {},
        "validation_folds": _validation_folds(selected, v7.period_start_utc, v7.period_end_utc, 30),
        "validation_status": "provisional_composite",
        "validation_reason": "Composite chart: V3 tick replay on Wednesday/Thursday and V7 exploratory intersection on other days. A unified replay is required for a decision-grade result.",
        "assumptions": v7.assumptions + ["V7.2: quarta e quinta UTC usam V3 pura; outros dias usam V7. Métricas são composição exploratória de replays distintos."],
    })
    (root / "data/backtests/core-zigzag-v72-365.json").write_text(output.model_dump_json(indent=2) + "\n")
    print(selected.__len__(), snapshot.summary.net_pnl, snapshot.summary.profit_factor)


if __name__ == "__main__":
    main()
