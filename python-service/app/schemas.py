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
    book: list[OrderBookLevel] = Field(default_factory=list, max_length=500)
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
    candles: list[CandleSnapshot] = Field(default_factory=list, max_length=5000)
    positions: list[PositionSnapshot] = Field(default_factory=list, max_length=100)
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
    active: bool = True


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
    risk_per_trade_pct: float = 0.0
    strategy_version: str = "legacy"
    settings_fingerprint: str = "legacy"
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


class EquityPoint(BaseModel):
    day: date
    cumulative_pnl: float


class EquitySeries(BaseModel):
    bot_id: str
    name: str
    strategy_profile: str
    summary: ResultsSummary
    points: list[EquityPoint] = Field(default_factory=list)


class EquityComparisonResponse(BaseModel):
    symbol: str
    timeframe: str
    period_days: int
    updated_at_utc: datetime
    series: list[EquitySeries] = Field(default_factory=list)
    missing_bot_ids: list[str] = Field(default_factory=list)


class GrowthPoint(BaseModel):
    day: date
    balance: float


class GrowthMilestone(BaseModel):
    balance_threshold: float
    risk_per_trade_pct: float
    reached_at_utc: datetime | None = None


class GrowthSimulationSeries(BaseModel):
    label: str
    initial_balance: float
    risk_per_trade_pct: float
    final_balance: float
    net_pnl: float
    return_pct: float
    max_drawdown: float
    max_drawdown_pct: float
    trades_simulated: int
    minimum_balance: float = 0.0
    milestones: list[GrowthMilestone] = Field(default_factory=list)
    points: list[GrowthPoint] = Field(default_factory=list)


class GrowthSimulationResponse(BaseModel):
    bot_id: str
    bot_name: str
    period_start_utc: datetime
    period_end_utc: datetime
    reference: GrowthSimulationSeries
    simulation: GrowthSimulationSeries


class RiskTier(BaseModel):
    balance_threshold: float = Field(..., ge=0, le=100_000_000)
    risk_per_trade_pct: float = Field(..., ge=0.01, le=10)


class GrowthSimulationRequest(BaseModel):
    initial_balance: float = Field(10000, ge=1, le=100_000_000)
    risk_tiers: list[RiskTier] = Field(default_factory=lambda: [RiskTier(balance_threshold=0, risk_per_trade_pct=0.25)], min_length=1, max_length=12)


class RuntimeStatusItem(BaseModel):
    bot_id: str
    name: str
    last_request_at_utc: datetime | None = None
    last_candle_at_utc: datetime | None = None
    last_action: str | None = None
    last_reason: str | None = None
    last_latency_ms: float | None = None
    consecutive_errors: int = 0
    last_error: str | None = None
    snapshot_updated_at_utc: datetime | None = None
    market_data_through_utc: datetime | None = None
    status: str = "no_data"


class OperationsResponse(BaseModel):
    updated_at_utc: datetime
    bots: list[RuntimeStatusItem] = Field(default_factory=list)
