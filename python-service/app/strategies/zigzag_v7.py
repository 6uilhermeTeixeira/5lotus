"""Frozen V7 directional gate, shared by decision engine and chart research."""
from datetime import timedelta

from ..indicators import ema, stochastic_series
from ..regime import classify_regime

PROFILE = "zigzag_scalper_v7_directional_shadow"


def context(candles, timestamp, side, settings, regime=None):
    completed = sorted((c for c in candles if c.timestamp_utc + timedelta(minutes=5) <= timestamp), key=lambda c: c.timestamp_utc)
    regime = regime if regime is not None else classify_regime(completed, settings)
    ready = len(completed) >= 60 and regime.name != "insufficient_history"
    regime_ok = ready and not (regime.name == "trend" and regime.direction == "sell")
    checks = {"h1_context": regime_ok}
    metadata = {"v7_regime": regime.name, "v7_direction": regime.direction, "v7_late_sell": side == "sell" and timestamp.hour >= 12}
    if side == "sell":
        closes = [c.close for c in completed[-50:]]
        checks["m5_below_ema50"] = ready and closes[-1] < ema(closes, 50)
        k, d = stochastic_series(completed[-60:]) if ready else ([], [])
        extreme = max(k[-2], d[-2]) if len(k) >= 2 else 0.0
        checks["late_stochastic_65"] = timestamp.hour < 12 or (ready and extreme >= 65)
        metadata["v7_previous_stochastic_extreme"] = extreme
    return all(checks.values()), checks, metadata


def evaluate(request, settings):
    from .. import strategy as engine
    # Give V5 an explicit current candle, even for closed-candle replay input.
    completed = sorted((c for c in request.candles if c.timestamp_utc + timedelta(minutes=5) <= request.timestamp_utc), key=lambda c: c.timestamp_utc)
    if len(completed) < 60:
        return engine.DecisionResponse(action=engine.DecisionAction.HOLD, reason="v7_warmup", metadata={"candidate": False, "strategy_profile": PROFILE})
    last = completed[-1].model_copy(update={"timestamp_utc": request.timestamp_utc, "open": request.bid, "high": request.bid, "low": request.bid, "close": request.bid})
    base = engine._evaluate_zigzag_scalper_v5(request.model_copy(update={"candles": completed[-60:] + [last]}), settings)
    side = str(base.metadata.get("suggested_action", ""))
    allowed, checks, metadata = context(completed, request.timestamp_utc, side, settings)
    base.risk_checks.extend(engine.RiskCheck(name="v7_" + name, passed=passed, detail=name) for name, passed in checks.items())
    if base.metadata.get("candidate"):
        base.metadata["candidate"] = allowed
        base.reason = "v7_shadow_signal" if allowed else "v7_directional_block"
    base.action = engine.DecisionAction.HOLD
    base.size = 0.0
    base.metadata.update(metadata | {"strategy_profile": PROFILE, "experimental_shadow_lock": True, "research_status": "provisional_requires_independent_replay"})
    return base
