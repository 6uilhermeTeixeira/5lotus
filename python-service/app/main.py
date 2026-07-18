import logging
from datetime import datetime, timezone

from fastapi import FastAPI

from .config import get_settings
from .schemas import DecisionRequest, DecisionResponse, HealthResponse
from .strategy import evaluate_decision

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger("daytrade.strategy")
settings = get_settings()
app = FastAPI(title=settings.app_name)


@app.get("/health", response_model=HealthResponse)
def healthcheck() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        timestamp_utc=datetime.now(timezone.utc),
    )


@app.get("/config")
def read_config() -> dict[str, str | int | float | bool]:
    return {
        "app_name": settings.app_name,
        "host": settings.host,
        "port": settings.port,
        "strategy_profile": settings.strategy_profile,
        "default_symbol": settings.default_symbol,
        "default_timeframe": settings.default_timeframe,
        "max_spread_points": settings.max_spread_points,
        "risk_per_trade_pct": settings.risk_per_trade_pct,
        "min_risk_reward": settings.min_risk_reward,
        "enable_live_decisions": settings.enable_live_decisions,
    }


@app.post("/decision", response_model=DecisionResponse)
def decision(payload: DecisionRequest) -> DecisionResponse:
    response = evaluate_decision(payload, settings)
    logger.info(
        "decision request_id=%s symbol=%s timeframe=%s action=%s reason=%s",
        payload.request_id,
        payload.symbol,
        payload.timeframe,
        response.action.value,
        response.reason,
    )
    return response
