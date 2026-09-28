"""Frozen research candidates; prices are USD/oz, timestamps milliseconds.

This module has no order-routing integration. Entry masks are causal and exits
use executable Bid/Ask observations, including adverse fills through stops.
"""
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Candidate:
    name: str
    confirm_quote: bool = False
    persistence_ms: int = 0
    efficiency_min: float = 0.0
    scaled_exit: bool = False


CANDIDATES = (
    Candidate("v3_ticks"),
    Candidate("v4_quote_confirm", True),
    Candidate("v4_persist_500ms", True, 500),
    Candidate("v4_persist_2000ms", True, 2000),
    Candidate("v4_efficiency", True, 500, .15),
    Candidate("v4_volatility_scaled", True, 500, 0.0, True),
)


def persistence(t, condition, bucket):
    """Elapsed time since first true observation; reset on false or new M5."""
    reset = (~condition) | np.r_[True, bucket[1:] != bucket[:-1]]
    starts = condition & np.r_[True, ~condition[:-1]]
    anchor = np.maximum.accumulate(np.where(reset | starts, np.arange(len(t)), 0))
    return np.where(condition, t - t[anchor], 0)


def exit_trade(t, bid, ask, index, direction, *, stop, target=10.0,
               be=.4, offset=0.0, activation=1.2, trail=.6,
               hold_ms=600_000, slippage=.02, risk_usd=24.0):
    """A moved stop becomes effective only after its triggering quote.

    Stop and time exits fill at the observed executable quote with slippage;
    take-profit is conservatively capped at its limit, without price improvement.
    Fixed risk has fractional research lots (no compounding/broker lot rounding).
    """
    end = min(int(np.searchsorted(t, t[index] + hold_ms, side="left")), len(t) - 1)
    entry = float((ask[index] if direction == 1 else bid[index]) + direction * slippage)
    prices = bid[index:end + 1] if direction == 1 else ask[index:end + 1]
    move = direction * (prices - entry)
    best = np.maximum.accumulate(move)
    previous_best = np.r_[-np.inf, best[:-1]]
    barrier = np.full(len(move), -stop)
    barrier = np.where(previous_best >= be, np.maximum(barrier, offset), barrier)
    barrier = np.where(previous_best >= activation, np.maximum(barrier, previous_best - trail), barrier)
    hits = np.flatnonzero((move <= barrier) | (move >= target))
    k = int(hits[0]) if len(hits) else len(move) - 1
    reason = "target" if move[k] >= target else "stop" if move[k] <= barrier[k] else "time"
    realized = target if reason == "target" else float(move[k]) - slippage
    lot = risk_usd / (100.0 * stop)
    fees = 4.5 * lot
    pnl = realized * 100 * lot - fees
    return {
        "entry_ms": int(t[index]), "exit_ms": int(t[index + k]),
        "direction": direction, "entry": entry,
        "exit": float(prices[k]), "stop_usd": stop, "lot": lot,
        "net_pnl": float(pnl), "r": float(pnl / risk_usd),
        "mfe_r": float(max(0, np.max(move[:k + 1])) / stop),
        "mae_r": float(max(0, -np.min(move[:k + 1])) / stop),
        "exit_reason": reason, "fees": fees,
        "max_quote_gap_ms": int(np.max(np.diff(t[index:index+k+1]))) if k else 0,
    }
