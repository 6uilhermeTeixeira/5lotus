"""Build the provisional V5.2 buy-context replay from frozen V5 fills.

This is a selection study, not a regenerated tick execution replay.  It keeps
only V5 buys whose last completed M5 close is at least one ATR14 above EMA50
and whose completed H1 regime is not directed down.
"""

from __future__ import annotations

from bisect import bisect_right
from pathlib import Path

from app.backtest import _risk_diagnostics, _validation_folds
from app.config import get_settings
from app.history_sync import load_m5_candles
from app.indicators import atr, ema
from app.local_dataset import DatasetRelease
from app.regime import _classify_hourly, _hourly_candles
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
    hourly = _hourly_candles(candles)
    hourly_timestamps = [candle.timestamp_utc for candle in hourly]
    threshold = float(settings.zigzag_scalper_v52_buy_ema50_distance_atr)
    kept: list[TradeResult] = []
    blocked = 0

    for trade in source.trades:
        if trade.side.value != "buy":
            kept.append(trade)
            continue
        index = bisect_right(timestamps, trade.opened_at_utc) - 1
        completed = candles[max(0, index - 49):index + 1]
        ema50 = ema([candle.close for candle in completed], 50) if len(completed) == 50 else None
        atr14 = atr(completed[-15:], 14) if len(completed) >= 15 else None
        distance_atr = (
            (completed[-1].close - ema50) / atr14
            if completed and ema50 is not None and atr14 else None
        )
        hour_index = bisect_right(hourly_timestamps, trade.opened_at_utc) - 1
        regime = _classify_hourly(hourly[max(0, hour_index - 319):hour_index + 1], settings)
        allowed = (
            regime.name != "insufficient_history"
            and regime.direction != "sell"
            and distance_atr is not None
            and distance_atr >= threshold
        )
        if not allowed:
            blocked += 1
            continue
        kept.append(trade.model_copy(update={
            "trade_id": trade.trade_id.replace("core-zigzag-v5", "core-zigzag-v9"),
            "setup": f"{trade.setup}; v52_buy_context",
            "note": (
                f"{trade.note} V5.2: compra aprovada; regime H1={regime.name}:{regime.direction}; "
                f"distância EMA50={distance_atr:.3f} ATR."
            ),
        }))

    snapshot = build_results_snapshot([trade.model_dump(mode="json") for trade in kept], "v52-derived-v5-buy-context")
    expectancy, max_drawdown, max_loss_streak, total_costs = _risk_diagnostics(kept)
    output = source.model_copy(update={
        "bot_id": "core-zigzag-v9",
        "strategy_version": "2026-09-15-v52-v5-buy-context",
        "settings_fingerprint": "v52-provisional-derived-chart-replay",
        "candidates_detected": len(source.trades),
        "candidates_eligible": len(kept),
        "candidates_blocked": blocked,
        "blocked_reasons": {"v52_buy_context_block": blocked},
        "expectancy_r": expectancy,
        "max_drawdown_r": max_drawdown,
        "max_consecutive_losses": max_loss_streak,
        "total_costs": total_costs,
        "validation_status": "provisional_shadow",
        "validation_reason": "derived V5.2 chart replay; requires a regenerated causal tick replay and independent walk-forward",
        "validation_folds": _validation_folds(kept, source.period_start_utc, source.period_end_utc, 30),
        "summary": snapshot.summary,
        "daily_pnl": snapshot.daily_pnl,
        "trades": kept,
        "assumptions": source.assumptions + [
            "V5.2 retains V5 sells and admits buys only when the completed H1 direction is not sell and the completed M5 close is at least 1.0 ATR14 above EMA50.",
            "Entries, exits, position sizing and tick fills are inherited from V5; this is not an independent execution replay.",
        ],
    })
    target = ROOT / "data/backtests/core-zigzag-v9-365.json"
    target.write_text(output.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"{target}: {len(kept)} retained trades; {blocked} buy trades blocked by V5.2 context")


if __name__ == "__main__":
    main()
