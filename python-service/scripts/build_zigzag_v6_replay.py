"""Build the V6 chart replay: V5 with the causal Stochastic V3 sell context."""

from __future__ import annotations

from bisect import bisect_right
from pathlib import Path

from app.backtest import _risk_diagnostics, _validation_folds
from app.config import get_settings
from app.history_sync import load_m5_candles
from app.indicators import ema
from app.local_dataset import DatasetRelease
from app.regime import build_regime_timeline, regime_at
from app.results_store import build_results_snapshot
from app.schemas import HistoricalReplayResponse, TradeResult


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    settings = get_settings()
    source = HistoricalReplayResponse.model_validate_json(
        (ROOT / "data/backtests/core-zigzag-v5-365.json").read_text(encoding="utf-8")
    )
    release = DatasetRelease.open(settings.lotus_data_root, settings.lotus_dataset_version)
    candles = load_m5_candles(release, "XAUUSD", 1095)
    timestamps = [candle.timestamp_utc for candle in candles]
    timeline = build_regime_timeline(candles, settings)
    kept: list[TradeResult] = []
    blocked = 0

    for trade in source.trades:
        if trade.side.value != "sell":
            kept.append(trade)
            continue
        # A trade opened at the end of M5 candle i can inspect up to candle i.
        index = bisect_right(timestamps, trade.opened_at_utc) - 1
        history = candles[max(0, index - 49):index + 1]
        close = history[-1].close if history else None
        ema50 = ema([item.close for item in history], 50) if len(history) == 50 else None
        regime = regime_at(timeline, trade.opened_at_utc)
        allowed = (
            trade.opened_at_utc.hour < settings.stochastic_sell_v3_cutoff_hour
            and regime.name != "insufficient_history"
            and not (regime.name == "trend" and regime.direction == "sell")
            and close is not None and ema50 is not None and close < ema50
        )
        if not allowed:
            blocked += 1
            continue
        kept.append(trade.model_copy(update={
            "trade_id": trade.trade_id.replace("core-zigzag-v5", "core-zigzag-v6"),
            "setup": f"{trade.setup}; v6_stochastic_v3_sell_context",
            "note": f"{trade.note} V6: venda aprovada pelo contexto Stochastic V3.",
        }))

    snapshot = build_results_snapshot([trade.model_dump(mode="json") for trade in kept], "v6-derived-v5-stochastic-context")
    expectancy, max_drawdown, max_loss_streak, total_costs = _risk_diagnostics(kept)
    output = source.model_copy(update={
        "bot_id": "core-zigzag-v6",
        "strategy_version": "2026-09-13-v6-v5-stochastic-v3-sell-context",
        "settings_fingerprint": "v6-provisional-derived-chart-replay",
        "candidates_detected": len(kept), "candidates_eligible": len(kept),
        "candidates_blocked": blocked, "blocked_reasons": {"v6_stochastic_v3_sell_gate_block": blocked},
        "expectancy_r": expectancy, "max_drawdown_r": max_drawdown, "max_consecutive_losses": max_loss_streak,
        "total_costs": total_costs, "validation_status": "provisional_shadow",
        "validation_reason": "derived V6 chart replay; requires independent walk-forward with Fusion ticks",
        "validation_folds": _validation_folds(kept, source.period_start_utc, source.period_end_utc, 30),
        "summary": snapshot.summary, "daily_pnl": snapshot.daily_pnl, "trades": kept,
        "assumptions": source.assumptions + ["V6 retains V5 buys and applies the causal Stochastic V3 context only to V5 sells."],
    })
    target = ROOT / "data/backtests/core-zigzag-v6-365.json"
    target.write_text(output.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"{target}: {len(kept)} retained trades; {blocked} sell trades blocked by Stochastic V3 context")


if __name__ == "__main__":
    main()
