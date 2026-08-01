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


class OrderBookLevel(BaseModel):
    side: str = Field(..., pattern="^(bid|ask)$")
    price: float
    volume: float


class FlowSnapshot(BaseModel):
    book: list[OrderBookLevel] = Field(default_factory=list)
    up_ticks: int = 0
    down_ticks: int = 0
    neutral_ticks: int = 0
    up_volume: float = 0.0
    down_volume: float = 0.0


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
    flow: FlowSnapshot | None = None


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
    partial_take_profit_price: float | None = None
    final_take_profit_price: float | None = None
    partial_close_pct: float = 0.0
    move_stop_to_breakeven: bool = False
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


class CandleIngestRequest(BaseModel):
    bot_id: str = Field(..., pattern=r"^[a-z0-9-]+$")
    symbol: str
    timeframe: str
    candles: list[CandleSnapshot] = Field(default_factory=list, max_length=1000)


class ReplayValidationFold(BaseModel):
    period_start_utc: datetime
    period_end_utc: datetime
    trades_count: int
    expectancy_r: float
    profit_factor: float
    net_pnl: float
    positive: bool


class HistoricalReplayResponse(BaseModel):
    bot_id: str
    symbol: str
    timeframe: str
    period_start_utc: datetime
    period_end_utc: datetime
    candles_evaluated: int
    candidates_detected: int
    candidates_eligible: int = 0
    candidates_blocked: int = 0
    regime_counts: dict[str, int] = Field(default_factory=dict)
    blocked_reasons: dict[str, int] = Field(default_factory=dict)
    expectancy_r: float = 0.0
    max_drawdown_r: float = 0.0
    max_consecutive_losses: int = 0
    forced_session_closes: int = 0
    total_costs: float = 0.0
    validation_status: str = "research_only"
    validation_reason: str = ""
    validation_folds: list[ReplayValidationFold] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    summary: ResultsSummary
    daily_pnl: list[DailyPnlPoint] = Field(default_factory=list)
    candles: list[CandleSnapshot] = Field(default_factory=list)
    trades: list[TradeResult] = Field(default_factory=list)
