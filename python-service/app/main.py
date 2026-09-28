import logging
from hmac import compare_digest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import monotonic

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .auth import has_valid_session
from .backtest import replay_settings_fingerprint
from .config import get_settings
from .growth import simulate_growth, simulate_tiered_growth
from .history_sync import HistoryRefreshInProgress, SUPPORTED_RESOLUTIONS, load_chart_candles, refresh_history
from .history_progress import load_dukascopy_progress, load_fusion_progress
from .local_dataset import DatasetError, DatasetRelease
from .local_backtest_store import load_local_backtest
from .routers.portal import create_portal_router
from .routers.replays import create_replay_router
from .routers.ingestion import create_ingestion_router
from .routers.operational import create_operational_router
from .routers.decision import create_decision_router
from .risk_normalization import normalize_replay_risk
from .results_store import build_results_snapshot, load_bots_catalog, load_results_snapshot, resolve_bot_results_file
from .security import RateLimit, client_key, rate_limiter, require_same_origin
from .services.comparison import build_equity_comparison
from .services.replays import load_cached_backtest, load_comparison_replay, load_local_replay_with_candles, scope_cached_replay
from .services.runtime import build_account_response, build_operations_response
from .services.decision_context import enforce_shadow_minimum, prepare_strategy_settings
from .schemas import AccountDashboardResponse, BacktestMarketChartResponse, BotCatalogItem, CandleIngestRequest, CandleSnapshot, DecisionRequest, DecisionResponse, EquityComparisonResponse, GrowthComparisonRequest, GrowthComparisonResponse, GrowthSimulationRequest, GrowthSimulationResponse, GrowthStrategySimulation, HealthResponse, HistoricalReplayResponse, HistoryRefreshResponse, MarketChartResponse, OperationsResponse, ResultsResponse, ResultsSummary, TickIngestRequest, TradeIngestRequest
from .strategy import ADAPTIVE_V3_COMBINED_PROFILE, HAPPY_GOLD_COMBINED_PROFILE, WEIGHTED_PORTFOLIO_PROFILES, evaluate_decision
from .strategies.registry import operational_bot_ids, strategy_definition, validate_active_catalog
from .supabase_store import SupabaseRequestError, SupabaseStore
from .telemetry import StepTimer, emit_event, metrics_snapshot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

logger = logging.getLogger("2lotus.strategy")
settings = get_settings()
app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parent / "static"), name="static")
BRAND_ICON_PATH = Path(__file__).resolve().parent / "static" / "brand" / "icon-1-black.png"
MAX_HISTORY_DAYS = 1095
OPERATIONAL_BOT_IDS = operational_bot_ids()


@app.middleware("http")
async def security_headers(request: Request, call_next):
    try:
        require_same_origin(request)
    except HTTPException as error:
        return JSONResponse(status_code=error.status_code, content={"detail": error.detail})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'self'; form-action 'self'"
    return response


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    return FileResponse(BRAND_ICON_PATH, media_type="image/png")


def _login_redirect() -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=303)


def _require_page_session(request: Request) -> RedirectResponse | None:
    if not settings.dashboard_auth_configured:
        return RedirectResponse(url="/login?error=config", status_code=303)
    return None if has_valid_session(request, settings) else _login_redirect()


def _require_api_session(request: Request) -> None:
    if not settings.dashboard_auth_configured:
        raise HTTPException(status_code=503, detail="dashboard authentication is not configured")
    if not has_valid_session(request, settings):
        raise HTTPException(status_code=401, detail="dashboard authentication required")


def _find_bot(bot_id: str, *, include_archived: bool = False) -> BotCatalogItem:
    bot = next((item for item in _list_bots(None if include_archived else True) if item.id == bot_id), None)
    if bot is None:
        raise HTTPException(status_code=404, detail="bot not found")
    return bot


def _uses_supabase_results() -> bool:
    return settings.results_store == "SUPABASE"


def _list_bots(active: bool | None = True) -> list[BotCatalogItem]:
    # The repository catalogs are versioned with the strategy engine.  The
    # database may lag behind a deploy, but that must not resurrect retired
    # rows or hide the preserved originals and newly shipped variants.
    bots = load_bots_catalog(settings.bots_catalog_path)
    if settings.legacy_bots_catalog_path.is_file():
        bots = load_bots_catalog(settings.legacy_bots_catalog_path) + bots
    validate_active_catalog(bots)
    return bots if active is None else [bot for bot in bots if bot.active is active]


def _load_bot_results(bot: BotCatalogItem) -> ResultsResponse:
    if _uses_supabase_results():
        return SupabaseStore(settings).load_results(bot.id)
    return load_results_snapshot(resolve_bot_results_file(settings.bots_catalog_path, bot))


app.include_router(create_portal_router(
    settings,
    list_bots=_list_bots,
    find_bot=_find_bot,
    require_page_session=_require_page_session,
    operational_bot_ids=OPERATIONAL_BOT_IDS,
))


def _replay_cache_matches_settings(replay: HistoricalReplayResponse, bot: BotCatalogItem | None = None) -> bool:
    if bot is not None and bot.strategy_profile == ADAPTIVE_V3_COMBINED_PROFILE:
        return replay.risk_per_trade_pct == 1.0 and replay.settings_fingerprint == replay_settings_fingerprint(settings, bot)
    risk_matches = round(replay.risk_per_trade_pct, 8) == round(settings.backtest_risk_per_trade_pct, 8)
    return risk_matches and (bot is None or replay.settings_fingerprint == replay_settings_fingerprint(settings, bot))


def _risk_scale_for_legacy_replay(bot: BotCatalogItem, replay: HistoricalReplayResponse) -> float | None:
    if bot.strategy_profile == ADAPTIVE_V3_COMBINED_PROFILE and replay.risk_per_trade_pct == 1.0:
        return 1.0
    if round(replay.risk_per_trade_pct, 8) == round(settings.backtest_risk_per_trade_pct, 8):
        return 1.0
    legacy_risk = replay.risk_per_trade_pct
    if legacy_risk <= 0 and bot.strategy_profile == HAPPY_GOLD_COMBINED_PROFILE:
        legacy_risk = 2.0
    if legacy_risk <= 0:
        return None
    return settings.backtest_risk_per_trade_pct / legacy_risk


def _normalize_replay_for_equity(bot: BotCatalogItem, replay: HistoricalReplayResponse) -> HistoricalReplayResponse | None:
    scale = _risk_scale_for_legacy_replay(bot, replay)
    if scale is None:
        return None
    if scale == 1.0:
        return replay
    normalized = replay.model_copy(deep=True)
    normalized.risk_per_trade_pct = settings.backtest_risk_per_trade_pct
    normalized.daily_pnl = [
        point.model_copy(update={"net_pnl": round(point.net_pnl * scale, 2)})
        for point in normalized.daily_pnl
    ]
    normalized.summary = ResultsSummary(
        trades_count=replay.summary.trades_count,
        wins=replay.summary.wins,
        losses=replay.summary.losses,
        breakevens=replay.summary.breakevens,
        open_positions=replay.summary.open_positions,
        win_rate_pct=replay.summary.win_rate_pct,
        gross_profit=round(replay.summary.gross_profit * scale, 2),
        gross_loss=round(replay.summary.gross_loss * scale, 2),
        net_pnl=round(replay.summary.net_pnl * scale, 2),
        avg_win=round(replay.summary.avg_win * scale, 2),
        avg_loss=round(replay.summary.avg_loss * scale, 2),
        profit_factor=replay.summary.profit_factor,
        avg_rr=replay.summary.avg_rr,
        best_trade=round(replay.summary.best_trade * scale, 2),
        worst_trade=round(replay.summary.worst_trade * scale, 2),
    )
    return normalized


def _load_or_run_backtest_replay(store: SupabaseStore, bot: BotCatalogItem, days: int, *, include_candles: bool = False) -> HistoricalReplayResponse | None:
    cached = store.load_backtest_snapshot(bot.id, days)
    if cached is not None and _replay_cache_matches_settings(cached, bot):
        if include_candles:
            cached.candles = store.load_candles(bot, settings.chart_cache_limit)
        return cached
    return None


def _load_cached_backtest(bot: BotCatalogItem, days: int, mode: str = "normalized") -> HistoricalReplayResponse | None:
    return load_cached_backtest(
        settings, bot, days, mode, uses_supabase=_uses_supabase_results(),
        store_factory=SupabaseStore, local_loader=load_local_backtest,
    )


def _scope_cached_replay(replay: HistoricalReplayResponse, days: int) -> HistoricalReplayResponse:
    return scope_cached_replay(replay, days, results_builder=build_results_snapshot)


def _load_comparison_replay(bot: BotCatalogItem, days: int, mode: str) -> HistoricalReplayResponse | None:
    return load_comparison_replay(
        bot, days, mode, max_history_days=MAX_HISTORY_DAYS,
        load_cached=_load_cached_backtest, scope_replay=_scope_cached_replay,
        normalize_risk=normalize_replay_risk,
    )


def _load_local_replay_with_candles(bot: BotCatalogItem, days: int) -> HistoricalReplayResponse | None:
    return load_local_replay_with_candles(
        settings, bot, days, load_cached=_load_cached_backtest,
        scope_replay=_scope_cached_replay, dataset_open=DatasetRelease.open,
        chart_loader=load_chart_candles,
    )


def _require_ingest_key(provided_key: str | None) -> None:
    if not settings.ingest_api_key:
        raise HTTPException(status_code=503, detail="trade ingestion is not configured")
    if not provided_key or not compare_digest(provided_key, settings.ingest_api_key):
        raise HTTPException(status_code=401, detail="invalid trade ingestion key")


def _validate_ingested_candles(candles: list[CandleSnapshot]) -> None:
    for candle in candles:
        prices = (candle.open, candle.high, candle.low, candle.close)
        if min(prices) <= 0:
            raise HTTPException(status_code=422, detail="OHLC prices must be positive")
        if candle.low > min(candle.open, candle.close) or candle.high < max(candle.open, candle.close) or candle.low > candle.high:
            raise HTTPException(status_code=422, detail="OHLC values are inconsistent")


@app.get("/api/history/progress")
def read_history_progress(request: Request, source: str = "dukascopy") -> dict[str, object]:
    _require_api_session(request)
    if source == "dukascopy":
        return load_dukascopy_progress(settings.lotus_data_root)
    if source == "fusion":
        return load_fusion_progress(settings.fusion_tick_spool_root, settings.fusion_history_collector_id)
    raise HTTPException(status_code=404, detail="history source not found")


@app.get("/api/bots", response_model=list[BotCatalogItem])
def read_bots(request: Request, archived: bool = False) -> list[BotCatalogItem]:
    _require_api_session(request)
    if archived:
        raise HTTPException(status_code=410, detail="archived strategies were retired")
    return _list_bots(True)


@app.get("/api/compare")
def read_comparison(request: Request) -> dict[str, object]:
    _require_api_session(request)
    bots = _list_bots()
    snapshots = []
    for bot in bots:
        results = _load_bot_results(bot)
        snapshots.append(
            {
                "id": bot.id,
                "name": bot.name,
                "strategy_profile": bot.strategy_profile,
                "symbol": bot.symbol,
                "timeframe": bot.timeframe,
                "latest_trade_at_utc": results.latest_trade_at_utc,
                "summary": results.summary.model_dump(mode="json"),
            }
        )
    return {"updated_at_utc": datetime.now(timezone.utc), "bots": snapshots}


def _build_equity_comparison(symbol: str, days: int, mode: str = "normalized") -> EquityComparisonResponse:
    normalized_symbol = symbol.upper()
    if days < 1 or days > MAX_HISTORY_DAYS:
        raise HTTPException(status_code=422, detail=f"comparison days must be between 1 and {MAX_HISTORY_DAYS}")
    if mode not in {"normalized", "operational"}:
        raise HTTPException(status_code=422, detail="comparison mode must be normalized or operational")
    bots = [bot for bot in _list_bots() if bot.symbol.upper() == normalized_symbol and bot.timeframe.upper() == "M5"]
    if not bots:
        raise HTTPException(status_code=404, detail="no bots configured for symbol")
    return build_equity_comparison(
        bots,
        symbol=normalized_symbol,
        timeframe="M5",
        period_days=days,
        load_replay=lambda bot: _load_comparison_replay(bot, days, mode),
    )


def read_equity_comparison(request: Request, symbol: str = "XAUUSD", days: int = 365, mode: str = "normalized") -> EquityComparisonResponse:
    _require_api_session(request)
    return _build_equity_comparison(symbol, days, mode)


def read_backtest_market_chart(
    request: Request, symbol: str = "XAUUSD", resolution: str = "5m", days: int = 30, mode: str = "normalized"
) -> BacktestMarketChartResponse:
    _require_api_session(request)
    if resolution not in SUPPORTED_RESOLUTIONS:
        raise HTTPException(status_code=422, detail="resolution must be one of 1m, 5m, 1h, 1d")
    if days < 1 or days > MAX_HISTORY_DAYS:
        raise HTTPException(status_code=422, detail=f"chart days must be between 1 and {MAX_HISTORY_DAYS}")
    equity = _build_equity_comparison(symbol, days, mode)
    dataset_version = "unavailable"
    candles = []
    try:
        release = DatasetRelease.open(settings.lotus_data_root, settings.lotus_dataset_version)
        dataset_version = release.version
        candles = load_chart_candles(release, symbol.upper(), resolution, days)
    except DatasetError:
        # Equity snapshots and market candles have independent lifecycles.  A
        # missing/unmounted dataset must not hide valid strategy performance.
        pass
    return BacktestMarketChartResponse(
        symbol=symbol.upper(), resolution=resolution, period_days=days,
        dataset_version=dataset_version, candles=candles,
        series=equity.series, missing_bot_ids=equity.missing_bot_ids,
    )


@app.post("/api/history/refresh", response_model=HistoryRefreshResponse)
def refresh_dashboard_history(request: Request, symbol: str = "XAUUSD", days: int = 365) -> HistoryRefreshResponse:
    _require_api_session(request)
    if days < 1 or days > MAX_HISTORY_DAYS:
        raise HTTPException(status_code=422, detail=f"history days must be between 1 and {MAX_HISTORY_DAYS}")
    rate_limiter.check(client_key(request, "history-refresh"), RateLimit(2, 300))
    try:
        return refresh_history(settings, symbol, days)
    except HistoryRefreshInProgress as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except DatasetError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/growth-simulation", response_model=GrowthSimulationResponse)
def read_growth_simulation(
    request: Request,
    initial_balance: float = 10000,
    risk_per_trade_pct: float = 0.25,
) -> GrowthSimulationResponse:
    _require_api_session(request)
    if not 100 <= initial_balance <= 100_000_000:
        raise HTTPException(status_code=422, detail="initial balance must be between 100 and 100000000")
    if not 0.01 <= risk_per_trade_pct <= 10:
        raise HTTPException(status_code=422, detail="risk per trade must be between 0.01 and 10")
    if not _uses_supabase_results():
        raise HTTPException(status_code=503, detail="growth simulation requires DAYTRADE_RESULTS_STORE=SUPABASE")
    bot = _find_bot("bot-16", include_archived=True)
    replay = SupabaseStore(settings).load_backtest_snapshot(bot.id, 365)
    if replay is None or not _replay_cache_matches_settings(replay, bot):
        raise HTTPException(status_code=503, detail="the annual 0.25 percent replay must be recalculated first")
    return GrowthSimulationResponse(
        bot_id=bot.id,
        bot_name=bot.name,
        period_start_utc=replay.period_start_utc,
        period_end_utc=replay.period_end_utc,
        reference=simulate_growth(replay, settings.backtest_balance, settings.backtest_risk_per_trade_pct, label="Referência"),
        simulation=simulate_growth(replay, initial_balance, risk_per_trade_pct, label="Simulação"),
    )


@app.post("/api/growth-simulation", response_model=GrowthSimulationResponse)
def create_growth_simulation(payload: GrowthSimulationRequest, request: Request) -> GrowthSimulationResponse:
    _require_api_session(request)
    if not _uses_supabase_results():
        raise HTTPException(status_code=503, detail="growth simulation requires DAYTRADE_RESULTS_STORE=SUPABASE")
    tiers = sorted(payload.risk_tiers, key=lambda tier: tier.balance_threshold)
    if tiers[0].balance_threshold > payload.initial_balance:
        raise HTTPException(status_code=422, detail="the first tier must start at or below the initial balance")
    if any(tiers[index].risk_per_trade_pct > tiers[index - 1].risk_per_trade_pct for index in range(1, len(tiers))):
        raise HTTPException(status_code=422, detail="risk must stay equal or decrease at higher balance tiers")
    bot = _find_bot("bot-16")
    replay = SupabaseStore(settings).load_backtest_snapshot(bot.id, 365)
    if replay is None or not _replay_cache_matches_settings(replay, bot):
        raise HTTPException(status_code=503, detail="the annual replay cache is unavailable or stale")
    return GrowthSimulationResponse(
        bot_id=bot.id,
        bot_name=bot.name,
        period_start_utc=replay.period_start_utc,
        period_end_utc=replay.period_end_utc,
        reference=simulate_growth(replay, settings.backtest_balance, settings.backtest_risk_per_trade_pct, label="Referência"),
        simulation=simulate_tiered_growth(replay, payload.initial_balance, tiers, label="Simulação"),
    )


@app.post("/api/growth-comparison", response_model=GrowthComparisonResponse)
def create_growth_comparison(payload: GrowthComparisonRequest, request: Request) -> GrowthComparisonResponse:
    _require_api_session(request)
    tiers = sorted(payload.risk_tiers, key=lambda tier: tier.balance_threshold)
    if tiers[0].balance_threshold > payload.initial_balance:
        raise HTTPException(status_code=422, detail="the first tier must start at or below the initial balance")
    if any(tiers[index].risk_per_trade_pct > tiers[index - 1].risk_per_trade_pct for index in range(1, len(tiers))):
        raise HTTPException(status_code=422, detail="risk must stay equal or decrease at higher balance tiers")
    catalog = {bot.id: bot for bot in _list_bots()}
    output: list[GrowthStrategySimulation] = []
    missing: list[str] = []
    for bot_id in dict.fromkeys(payload.bot_ids):
        bot = catalog.get(bot_id)
        replay = _load_cached_backtest(bot, 365, payload.mode) if bot else None
        if bot is None or replay is None:
            missing.append(bot_id)
            continue
        cutoff = replay.period_end_utc - timedelta(days=payload.days)
        scoped = replay.model_copy(update={
            "period_start_utc": max(replay.period_start_utc, cutoff),
            "trades": [trade for trade in replay.trades if trade.opened_at_utc >= cutoff],
        })
        output.append(GrowthStrategySimulation(
            bot_id=bot.id, bot_name=bot.name, strategy_profile=bot.strategy_profile,
            simulation=simulate_tiered_growth(scoped, payload.initial_balance, tiers, label=bot.name),
        ))
    return GrowthComparisonResponse(mode=payload.mode, period_days=payload.days, series=output, missing_bot_ids=missing)


def read_operations(request: Request) -> OperationsResponse:
    _require_api_session(request)
    bots = _list_bots()
    store = SupabaseStore(settings)
    statuses, snapshots = store.load_operations()
    return build_operations_response(bots, statuses, snapshots, now=datetime.now(timezone.utc))


def read_account(request: Request) -> AccountDashboardResponse:
    _require_api_session(request)
    row = SupabaseStore(settings).load_latest_account_snapshot() if _uses_supabase_results() else None
    return build_account_response(
        row,
        expected_account_id=settings.mt5_login,
        expected_server=settings.mt5_server,
        initial_balance=settings.mt5_initial_balance,
        now=datetime.now(timezone.utc),
    )


@app.get("/api/bots/{bot_id}/results", response_model=ResultsResponse)
def read_bot_results(bot_id: str, request: Request) -> ResultsResponse:
    _require_api_session(request)
    return _load_bot_results(_find_bot(bot_id, include_archived=True))


@app.get("/api/bots/{bot_id}/chart", response_model=MarketChartResponse)
def read_bot_chart(bot_id: str, request: Request) -> MarketChartResponse:
    _require_api_session(request)
    bot = _find_bot(bot_id, include_archived=True)
    if not _uses_supabase_results():
        raise HTTPException(status_code=503, detail="chart data requires DAYTRADE_RESULTS_STORE=SUPABASE")
    return SupabaseStore(settings).load_chart(bot, settings.chart_cache_limit)


def read_historical_replay(bot_id: str, request: Request, days: int = 120) -> HistoricalReplayResponse:
    _require_api_session(request)
    if days < 1 or days > MAX_HISTORY_DAYS:
        raise HTTPException(status_code=422, detail=f"replay days must be between 1 and {MAX_HISTORY_DAYS}")
    bot = _find_bot(bot_id, include_archived=True)
    if not _uses_supabase_results():
        try:
            replay = _load_local_replay_with_candles(bot, days)
        except DatasetError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        if replay is None:
            raise HTTPException(status_code=404, detail="historical replay cache is unavailable")
        return replay
    store = SupabaseStore(settings)
    replay = _load_or_run_backtest_replay(store, bot, days, include_candles=True)
    if replay is None:
        # Research variants can ship with a frozen local replay before their
        # first Supabase publication.  Preserve the chart (including entries
        # and exits) in that interval instead of returning an empty page.
        try:
            replay = _load_local_replay_with_candles(bot, days)
        except DatasetError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
    if replay is None:
        raise HTTPException(status_code=404, detail="no historical candles available for replay")
    return replay


app.include_router(create_replay_router(
    equity_comparison=read_equity_comparison,
    market_chart=read_backtest_market_chart,
    historical_replay=read_historical_replay,
))


@app.get("/api/results", response_model=ResultsResponse, deprecated=True)
def read_legacy_results(request: Request) -> ResultsResponse:
    _require_api_session(request)
    bots = _list_bots()
    if not bots:
        raise HTTPException(status_code=404, detail="no bots configured")
    return _load_bot_results(bots[0])


def ingest_trade(payload: TradeIngestRequest, request: Request, x_2lotus_ingest_key: str | None = Header(default=None)) -> None:
    rate_limiter.check(client_key(request, "ingest"), RateLimit(settings.ingest_rate_limit_per_minute, 60))
    _require_ingest_key(x_2lotus_ingest_key)
    if not _uses_supabase_results():
        raise HTTPException(status_code=503, detail="trade ingestion requires DAYTRADE_RESULTS_STORE=SUPABASE")
    _find_bot(payload.bot_id)
    SupabaseStore(settings).upsert_trade(payload.bot_id, payload.trade)


def ingest_candles(payload: CandleIngestRequest, request: Request, x_2lotus_ingest_key: str | None = Header(default=None)) -> None:
    rate_limiter.check(client_key(request, "ingest"), RateLimit(settings.ingest_rate_limit_per_minute, 60))
    _require_ingest_key(x_2lotus_ingest_key)
    _validate_ingested_candles(payload.candles)
    if not _uses_supabase_results():
        raise HTTPException(status_code=503, detail="candle ingestion requires DAYTRADE_RESULTS_STORE=SUPABASE")
    bot = _find_bot(payload.bot_id)
    if bot.symbol != payload.symbol or bot.timeframe != payload.timeframe:
        raise HTTPException(status_code=422, detail="candle symbol or timeframe does not match bot configuration")
    SupabaseStore(settings).upsert_candles(payload.bot_id, payload.symbol, payload.timeframe, payload.candles)


def ingest_ticks(payload: TickIngestRequest, request: Request, x_2lotus_ingest_key: str | None = Header(default=None)) -> None:
    rate_limiter.check(client_key(request, "tick_ingest"), RateLimit(settings.tick_ingest_rate_limit_per_minute, 60))
    _require_ingest_key(x_2lotus_ingest_key)
    if not _uses_supabase_results():
        raise HTTPException(status_code=503, detail="tick ingestion requires DAYTRADE_RESULTS_STORE=SUPABASE")
    store = SupabaseStore(settings)
    store.upsert_ticks(payload)
    store.advance_tick_shadow_trades(payload)


app.include_router(create_ingestion_router(
    ingest_trade_handler=ingest_trade,
    ingest_candles_handler=ingest_candles,
    ingest_ticks_handler=ingest_ticks,
))


def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok", service=settings.app_name, timestamp_utc=datetime.now(timezone.utc))


def readiness() -> JSONResponse:
    checks: dict[str, object] = {
        "configuration": "passed",
        "supabase": "disabled" if not _uses_supabase_results() else "not_checked",
        "dataset": "not_checked",
        "local_backtests": "not_checked",
    }
    try:
        release = DatasetRelease.open(settings.lotus_data_root, settings.lotus_dataset_version)
        checks["dataset"] = "passed"
        checks["dataset_version"] = release.version
    except (DatasetError, OSError, ValueError):
        checks["dataset"] = "failed"

    active_bots = [bot for bot in _list_bots() if bot.symbol.upper() == settings.default_symbol.upper()]
    local_snapshots = sum(
        1 for bot in active_bots
        if load_local_backtest(settings.backtest_cache_path, bot.id, 365) is not None
    )
    checks["local_backtests"] = (
        "passed" if active_bots and local_snapshots == len(active_bots)
        else "partial" if local_snapshots
        else "failed"
    )
    checks["local_backtests_available"] = local_snapshots
    checks["local_backtests_expected"] = len(active_bots)

    if _uses_supabase_results():
        if not settings.supabase_results_configured:
            checks["configuration"] = "failed"
            return JSONResponse(status_code=503, content={"status": "not_ready", "checks": checks})
        try:
            SupabaseStore(settings).readiness()
            checks["supabase"] = "passed"
        except SupabaseRequestError as error:
            checks["supabase"] = error.code
            return JSONResponse(status_code=503, content={"status": "not_ready", "checks": checks})
    status_code = 200 if checks["dataset"] == "passed" and local_snapshots else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if status_code == 200 else "not_ready", "checks": checks},
    )


def read_metrics(request: Request) -> dict[str, object]:
    _require_api_session(request)
    return metrics_snapshot()


def read_config(request: Request) -> dict[str, str | int | float | bool]:
    _require_api_session(request)
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
        "fimath_mode": settings.fimath_mode,
        "fimath_flow_window_seconds": settings.fimath_flow_window_seconds,
        "fimath_flow_min_samples": settings.fimath_flow_min_samples,
        "fimath_flow_z_threshold": settings.fimath_flow_z_threshold,
        "fimath_flow_policy": settings.fimath_flow_policy,
        "fimath_partial_pct": settings.fimath_partial_pct,
        "fimath_min_closed_paper_trades": settings.fimath_min_closed_paper_trades,
        "chart_cache_limit": settings.chart_cache_limit,
        "backtest_balance": settings.backtest_balance,
        "backtest_spread_points": settings.backtest_spread_points,
        "backtest_candle_limit": settings.backtest_candle_limit,
        "backtest_risk_per_trade_pct": settings.backtest_risk_per_trade_pct,
        "backtest_slippage_points": settings.backtest_slippage_points,
        "backtest_commission_per_lot": settings.backtest_commission_per_lot,
        "backtest_session_start_utc": settings.backtest_session_start_utc,
        "backtest_session_end_utc": settings.backtest_session_end_utc,
        "backtest_regime_enabled": settings.backtest_regime_enabled,
        "happy_gold_break_even_trigger_points": settings.happy_gold_break_even_trigger_points,
        "happy_gold_break_even_offset_points": settings.happy_gold_break_even_offset_points,
        "happy_gold_trailing_activation_points": settings.happy_gold_trailing_activation_points,
        "happy_gold_trailing_distance_points": settings.happy_gold_trailing_distance_points,
        "happy_gold_max_holding_bars": settings.happy_gold_max_holding_bars,
        "happy_gold_combined_session_start_utc": settings.happy_gold_combined_session_start_utc,
        "happy_gold_combined_session_end_utc": settings.happy_gold_combined_session_end_utc,
        "enable_live_decisions": settings.enable_live_decisions,
        "dashboard_auth_configured": settings.dashboard_auth_configured,
        "results_store": settings.results_store,
        "supabase_results_configured": settings.supabase_results_configured,
    }


app.include_router(create_operational_router(
    operations_handler=read_operations,
    account_handler=read_account,
    health_handler=healthcheck,
    readiness_handler=readiness,
    metrics_handler=read_metrics,
    config_handler=read_config,
))


def decision(payload: DecisionRequest, request: Request, x_2lotus_ingest_key: str | None = Header(default=None)) -> DecisionResponse:
    run_id = payload.request_id
    started_at = monotonic()
    run_timer = StepTimer(run_id, "decision_run")
    rate_limiter.check(client_key(request, "ingest"), RateLimit(settings.ingest_rate_limit_per_minute, 60))
    _require_ingest_key(x_2lotus_ingest_key)
    _validate_ingested_candles(payload.candles)
    store: SupabaseStore | None = None
    strategy_profile = settings.strategy_profile
    try:
        if payload.bot_id and _uses_supabase_results():
            bot = _find_bot(payload.bot_id)
            strategy_profile = bot.strategy_profile
            if bot.symbol != payload.symbol or bot.timeframe != payload.timeframe:
                raise HTTPException(status_code=422, detail="decision symbol or timeframe does not match bot configuration")
            store = SupabaseStore(settings)
            try:
                store.upsert_account_snapshot(payload.account, payload.timestamp_utc)
            except SupabaseRequestError as telemetry_error:
                emit_event(run_id=run_id, step="persist_account_snapshot", status="failed", error_code=telemetry_error.code, bot_id=payload.bot_id)
            cached_response = store.load_decision_response(payload.bot_id, payload.request_id)
            if cached_response is not None:
                emit_event(run_id=run_id, step="idempotency_lookup", status="replayed", bot_id=payload.bot_id)
                try:
                    store.record_runtime_status(payload.bot_id, request_at=payload.timestamp_utc, candle_at=payload.candles[-1].timestamp_utc if payload.candles else None, action=cached_response.action.value, reason=cached_response.reason, latency_ms=(monotonic() - started_at) * 1000)
                except SupabaseRequestError as telemetry_error:
                    emit_event(run_id=run_id, step="persist_runtime_status", status="failed", error_code=telemetry_error.code, bot_id=payload.bot_id)
                run_timer.finish(status="passed", bot_id=payload.bot_id, outcome="idempotent_replay")
                return cached_response
            store.upsert_candles(payload.bot_id, payload.symbol, payload.timeframe, payload.candles)
            store.advance_paper_trades(payload.bot_id, payload.candles)
            definition = strategy_definition(strategy_profile)
            decision_history_bars = definition.decision_history_bars if definition is not None else None
            if decision_history_bars is None and strategy_profile in {"happy_gold_zigzag_regime_confirmed", HAPPY_GOLD_COMBINED_PROFILE, *WEIGHTED_PORTFOLIO_PROFILES}:
                decision_history_bars = 4000
            if decision_history_bars is not None:
                payload.candles = store.load_candles(
                    bot,
                    decision_history_bars,
                )
        portfolio_risk_state = None
        if payload.bot_id:
            definition = strategy_definition(strategy_profile)
            uses_portfolio_state = definition is not None and definition.regime_policy == "internal_portfolio"
            if (uses_portfolio_state or strategy_profile in WEIGHTED_PORTFOLIO_PROFILES or strategy_profile == HAPPY_GOLD_COMBINED_PROFILE) and store:
                portfolio_risk_state = store.load_portfolio_risk_state(payload.bot_id, payload.timestamp_utc)
        strategy_settings = prepare_strategy_settings(
            settings,
            payload,
            strategy_profile,
            portfolio_risk_state=portfolio_risk_state,
        )
        response = evaluate_decision(payload, strategy_settings, strategy_profile)
        if payload.bot_id and store and response.metadata.get("candidate"):
            signal_key = store.record_strategy_candidate(payload, response)
            if signal_key and response.metadata.get("tick_shadow_lifecycle"):
                store.record_tick_shadow_trade(signal_key, payload, response)
            if signal_key and response.metadata.get("record_paper_trade", True):
                store.record_paper_trade(signal_key, payload, response, "technical")
                if response.metadata.get("flow_confirmed"):
                    store.record_paper_trade(signal_key, payload, response, "flow_confirmed")
        if payload.bot_id and store and response.parallel_candidates:
            for parallel_response in response.parallel_candidates:
                component = str(parallel_response.metadata.get("combined_component", "component"))
                signal_key = store.record_strategy_candidate(payload, parallel_response)
                if signal_key:
                    store.record_paper_trade(signal_key, payload, parallel_response, f"parallel:{component}")
        if payload.bot_id and store and response.action.value in {"buy", "sell"}:
            validation_variant = "flow_confirmed" if strategy_profile == "fimath_ema20_flow" and settings.fimath_flow_policy == "required" else "technical"
            closed_count = store.closed_paper_trade_count(payload.bot_id, validation_variant)
            enforce_shadow_minimum(
                response,
                validation_variant=validation_variant,
                closed_paper_trades=closed_count,
                minimum_closed_trades=settings.fimath_min_closed_paper_trades,
            )
        if payload.bot_id and store:
            store.save_decision_response(payload.bot_id, payload.request_id, response)
            try:
                store.record_runtime_status(payload.bot_id, request_at=payload.timestamp_utc, candle_at=payload.candles[-1].timestamp_utc if payload.candles else None, action=response.action.value, reason=response.reason, latency_ms=(monotonic() - started_at) * 1000)
            except SupabaseRequestError as telemetry_error:
                emit_event(run_id=run_id, step="persist_runtime_status", status="failed", error_code=telemetry_error.code, bot_id=payload.bot_id)
        run_timer.finish(status="passed", bot_id=payload.bot_id, outcome=response.reason)
        return response
    except SupabaseRequestError as error:
        run_timer.finish(status="failed", bot_id=payload.bot_id, error_code=error.code)
        if payload.bot_id and store:
            try:
                store.record_runtime_failure(payload.bot_id, error_code=error.code, error_message=str(error))
            except SupabaseRequestError:
                pass
        raise HTTPException(status_code=503, detail=f"decision dependency unavailable: {error.code}") from error


app.include_router(create_decision_router(decision_handler=decision))
