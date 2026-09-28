"""Build the V8 accuracy-cycle chart from the V7.2 exploratory composite."""
from pathlib import Path

from app.backtest import _risk_diagnostics, _validation_folds
from app.results_store import build_results_snapshot
from app.schemas import HistoricalReplayResponse
from app.strategies.zigzag_v8 import calendar_allows


def main():
    root = Path(__file__).resolve().parents[1]
    source = HistoricalReplayResponse.model_validate_json((root / "data/backtests/core-zigzag-v72-365.json").read_text())
    selected = []
    for trade in source.trades:
        if calendar_allows(trade.opened_at_utc, trade.side.value):
            selected.append(trade.model_copy(update={
                "trade_id": trade.trade_id.replace("core-zigzag-v72", "core-zigzag-v8"),
                "setup": "zigzag_v8_accuracy_cycle",
                "note": trade.note + " V8: calendário semanal mensal de assertividade.",
            }))
    snapshot = build_results_snapshot([t.model_dump(mode="json") for t in selected], "v8-accuracy-cycle")
    expectancy, drawdown, streak, costs = _risk_diagnostics(selected)
    output = source.model_copy(update={
        "bot_id": "core-zigzag-v8", "strategy_version": "v8-accuracy-cycle-1",
        "settings_fingerprint": "v8-accuracy-cycle-1", "trades": selected,
        "summary": snapshot.summary, "daily_pnl": snapshot.daily_pnl,
        "expectancy_r": expectancy, "max_drawdown_r": drawdown,
        "max_consecutive_losses": streak, "total_costs": costs,
        "candidates_detected": len(source.trades), "candidates_eligible": len(selected),
        "candidates_blocked": len(source.trades) - len(selected),
        "blocked_reasons": {"v8_accuracy_cycle": len(source.trades) - len(selected)},
        "regime_counts": {},
        "validation_folds": _validation_folds(selected, source.period_start_utc, source.period_end_utc, 30),
        "validation_status": "provisional_shadow",
        "validation_reason": "V8 calendar replay is derived from the V7.2 composite; requires unified replay and forward validation.",
        "assumptions": source.assumptions + ["V8: semana 2 segunda, semana 3 terça somente compras, semana 4 sexta; demais semanas/dias bloqueados."],
    })
    (root / "data/backtests/core-zigzag-v8-365.json").write_text(output.model_dump_json(indent=2) + "\n")
    print(len(selected), snapshot.summary.win_rate_pct, snapshot.summary.profit_factor, snapshot.summary.net_pnl)


if __name__ == "__main__":
    main()
