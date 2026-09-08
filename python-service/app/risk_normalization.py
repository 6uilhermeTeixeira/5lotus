from __future__ import annotations

from datetime import datetime

from .backtest import _risk_diagnostics, _validation_folds
from .results_store import build_results_snapshot
from .schemas import HistoricalReplayResponse, TradeResult


def normalize_replay_risk(replay: HistoricalReplayResponse, risk_pct: float = 1.0) -> HistoricalReplayResponse:
    """Keep signals and realized R unchanged while sizing every entry at one risk percentage."""
    events: list[tuple[datetime, int, TradeResult]] = []
    for trade in replay.trades:
        if trade.closed_at_utc is None:
            continue
        events.extend(((trade.opened_at_utc, 0, trade), (trade.closed_at_utc, 1, trade)))
    events.sort(key=lambda event: (event[0], event[1]))
    balance = 10_000.0
    risks: dict[str, float] = {}
    normalized: list[TradeResult] = []
    for _, kind, trade in events:
        if kind == 0:
            risks[trade.trade_id] = balance * risk_pct / 100
            continue
        risk = risks.pop(trade.trade_id)
        pnl = round(risk * float(trade.rr_realized or 0), 2)
        scale = risk / trade.risk_amount if trade.risk_amount else 0
        normalized.append(trade.model_copy(update={
            "volume_lots": round(trade.volume_lots * scale, 4), "risk_amount": round(risk, 2),
            "gross_pnl": pnl, "fees": 0.0, "net_pnl": pnl,
            "note": f"Comparação normalizada; risco={risk_pct:g}% do patrimônio; {trade.note}",
        }))
        balance += pnl
    normalized.sort(key=lambda trade: trade.closed_at_utc or trade.opened_at_utc)
    result = build_results_snapshot([trade.model_dump(mode="json") for trade in normalized], "normalized")
    expectancy, drawdown, losses, costs = _risk_diagnostics(normalized)
    return replay.model_copy(update={
        "strategy_version": f"normalized_{risk_pct:g}pct", "risk_per_trade_pct": risk_pct,
        "summary": result.summary, "daily_pnl": result.daily_pnl, "trades": normalized,
        "expectancy_r": expectancy, "max_drawdown_r": drawdown, "max_consecutive_losses": losses,
        "total_costs": costs,
        "validation_folds": _validation_folds(normalized, replay.period_start_utc, replay.period_end_utc, 30),
        "assumptions": [
            "Comparação normalizada: cada entrada arrisca 1% do patrimônio disponível.",
            "Sinais, stops, alvos e R realizado permanecem idênticos ao replay operacional.",
            "Lote fixo e multiplicadores internos são ignorados somente na camada comparativa.",
        ],
    })
