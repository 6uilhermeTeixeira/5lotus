from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class DecisionAction(str, Enum):
    HOLD = "hold"
    BUY = "buy"
    SELL = "sell"
    CLOSE = "close"


class PositionSnapshot(BaseModel):
    symbol: str
    side: str
    volume: float
    entry_price: float
    profit: float = 0.0


class AccountSnapshot(BaseModel):
    balance: float
    equity: float
    margin_free: float
    leverage: int | None = None


class CandleSnapshot(BaseModel):
    timestamp_utc: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class DecisionRequest(BaseModel):
    request_id: str = Field(..., min_length=3)
    timestamp_utc: datetime
    symbol: str
    timeframe: str
    bid: float
    ask: float
    spread_points: float
    point_size: float
    value_per_point_per_lot: float
    candles: list[CandleSnapshot] = Field(default_factory=list)
    positions: list[PositionSnapshot] = Field(default_factory=list)
    account: AccountSnapshot
    indicators: dict[str, float] = Field(default_factory=dict)


class RiskCheck(BaseModel):
    name: str
    passed: bool
    detail: str


class DecisionResponse(BaseModel):
    action: DecisionAction
    reason: str
    size: float = 0.0
    risk_amount: float = 0.0
    entry_price: float | None = None
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    stop_loss_points: float | None = None
    take_profit_points: float | None = None
    risk_checks: list[RiskCheck] = Field(default_factory=list)
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp_utc: datetime
