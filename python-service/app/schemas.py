from datetime import date, datetime
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
    bot_id: str | None = Field(default=None, pattern=r"^[a-z0-9-]+$")
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


class TradeSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class TradeResult(BaseModel):
    trade_id: str = Field(..., min_length=3)
    symbol: str
    timeframe: str
    setup: str
    side: TradeSide
    opened_at_utc: datetime
    closed_at_utc: datetime | None = None
    volume_lots: float
    entry_price: float
    exit_price: float | None = None
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    risk_amount: float = 0.0
    gross_pnl: float = 0.0
    fees: float = 0.0
    net_pnl: float = 0.0
    rr_realized: float | None = None
    note: str = ""


class MarketChartResponse(BaseModel):
    bot_id: str
    symbol: str
    timeframe: str
    candles: list[CandleSnapshot] = Field(default_factory=list)
    trades: list[TradeResult] = Field(default_factory=list)


class ResultsSummary(BaseModel):
    trades_count: int = 0
    wins: int = 0
    losses: int = 0
    breakevens: int = 0
    open_positions: int = 0
    win_rate_pct: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    avg_rr: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0


class DailyPnlPoint(BaseModel):
    day: date
    net_pnl: float


class ResultsResponse(BaseModel):
    source_file: str
    latest_trade_at_utc: datetime | None = None
    summary: ResultsSummary
    daily_pnl: list[DailyPnlPoint] = Field(default_factory=list)
    recent_trades: list[TradeResult] = Field(default_factory=list)


class BotCatalogItem(BaseModel):
    id: str = Field(..., pattern=r"^[a-z0-9-]+$")
    name: str
    description: str
    strategy_profile: str
    strategy_description: str = ""
    symbol: str
    timeframe: str
    results_file: str = ""


class TradeIngestRequest(BaseModel):
    bot_id: str = Field(..., pattern=r"^[a-z0-9-]+$")
    trade: TradeResult
