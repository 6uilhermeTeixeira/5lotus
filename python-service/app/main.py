import logging
from copy import copy
from hmac import compare_digest
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .auth import SESSION_COOKIE_NAME, create_session_value, has_valid_session, password_matches, read_login_password
from .backtest import run_historical_replay
from .config import get_settings
from .pages import render_catalog_page, render_comparison_page, render_login_page, render_results_page
from .results_store import get_bot, load_bots_catalog, load_results_snapshot, resolve_bot_results_file
from .schemas import BotCatalogItem, CandleIngestRequest, DecisionAction, DecisionRequest, DecisionResponse, EquityComparisonResponse, EquityPoint, EquitySeries, HealthResponse, HistoricalReplayResponse, MarketChartResponse, ResultsResponse, TradeIngestRequest
from .strategy import WEIGHTED_PORTFOLIO_PROFILES, evaluate_decision
from .supabase_store import SupabaseStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

logger = logging.getLogger("2lotus.strategy")
settings = get_settings()
app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parent / "static"), name="static")
BRAND_ICON_PATH = Path(__file__).resolve().parent / "static" / "brand" / "icon-1-black.png"


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
    if _uses_supabase_results():
        return SupabaseStore(settings).list_bots(active)
    bots = load_bots_catalog(settings.bots_catalog_path)
    return bots if active is None else [bot for bot in bots if bot.active is active]


def _load_bot_results(bot: BotCatalogItem) -> ResultsResponse:
    if _uses_supabase_results():
        return SupabaseStore(settings).load_results(bot.id)
    return load_results_snapshot(resolve_bot_results_file(settings.bots_catalog_path, bot))


def _market_data_source_bot_id(bot: BotCatalogItem) -> str:
    if bot.symbol.upper() == settings.default_symbol.upper() and bot.timeframe.upper() == settings.default_timeframe.upper():
        return settings.backtest_market_data_bot_id
    if bot.symbol.upper() == "EURUSD" and bot.timeframe.upper() == "M5":
        return "bot-eur-1"
    return bot.id


def _require_ingest_key(provided_key: str | None) -> None:
    if not settings.ingest_api_key:
        raise HTTPException(status_code=503, detail="trade ingestion is not configured")
    if not provided_key or not compare_digest(provided_key, settings.ingest_api_key):
        raise HTTPException(status_code=401, detail="invalid trade ingestion key")


@app.get("/", include_in_schema=False)
def root(request: Request) -> RedirectResponse:
    return RedirectResponse(url="/bots" if has_valid_session(request, settings) else "/login", status_code=303)


@app.get("/login", response_class=HTMLResponse, response_model=None, include_in_schema=False)
def login_page(request: Request, error: str | None = None) -> HTMLResponse | RedirectResponse:
    if has_valid_session(request, settings):
        return RedirectResponse(url="/bots", status_code=303)
    if error == "config" or not settings.dashboard_auth_configured:
        return render_login_page("O acesso ainda nao foi configurado neste ambiente.", status_code=503)
    return render_login_page()


@app.post("/login", response_model=None, include_in_schema=False)
async def login(request: Request) -> RedirectResponse | HTMLResponse:
    if not settings.dashboard_auth_configured:
        return render_login_page("O acesso ainda nao foi configurado neste ambiente.", status_code=503)
    if not password_matches(await read_login_password(request), settings):
        return render_login_page("Senha invalida.", status_code=401)
    response = RedirectResponse(url="/bots", status_code=303)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        create_session_value(settings),
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    return response


@app.post("/logout", include_in_schema=False)
def logout() -> RedirectResponse:
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


@app.get("/bots", response_class=HTMLResponse, response_model=None, include_in_schema=False)
def bots_page(request: Request) -> HTMLResponse | RedirectResponse:
    if redirect := _require_page_session(request):
        return redirect
    return render_catalog_page(_list_bots(True), _list_bots(False))


@app.get("/compare", response_class=HTMLResponse, response_model=None, include_in_schema=False)
def comparison_page(request: Request) -> HTMLResponse | RedirectResponse:
    if redirect := _require_page_session(request):
        return redirect
    return render_comparison_page(_list_bots())


@app.get("/bots/{bot_id}", response_class=HTMLResponse, response_model=None, include_in_schema=False)
def bot_results_page(bot_id: str, request: Request) -> HTMLResponse | RedirectResponse:
    if redirect := _require_page_session(request):
        return redirect
    return render_results_page(_find_bot(bot_id, include_archived=True))


@app.get("/results", include_in_schema=False)
def legacy_results(request: Request) -> RedirectResponse:
    if redirect := _require_page_session(request):
        return redirect
    bots = _list_bots()
    return RedirectResponse(url=f"/bots/{bots[0].id}" if bots else "/bots", status_code=303)


@app.get("/api/bots", response_model=list[BotCatalogItem])
def read_bots(request: Request, archived: bool = False) -> list[BotCatalogItem]:
    _require_api_session(request)
    return _list_bots(not archived)


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


@app.get("/api/equity-comparison", response_model=EquityComparisonResponse)
def read_equity_comparison(request: Request, symbol: str = "XAUUSD", days: int = 365) -> EquityComparisonResponse:
    _require_api_session(request)
    normalized_symbol = symbol.upper()
    if days < 1 or days > 365:
        raise HTTPException(status_code=422, detail="comparison days must be between 1 and 365")
    bots = [bot for bot in _list_bots() if bot.symbol.upper() == normalized_symbol and bot.timeframe.upper() == "M5"]
    if not bots:
        raise HTTPException(status_code=404, detail="no bots configured for symbol")
    if not _uses_supabase_results():
        raise HTTPException(status_code=503, detail="equity comparison requires DAYTRADE_RESULTS_STORE=SUPABASE")
    store = SupabaseStore(settings)
    series: list[EquitySeries] = []
    missing: list[str] = []
    for bot in bots:
        replay = store.load_backtest_snapshot(bot.id, days)
        if replay is None:
            missing.append(bot.id)
            continue
        cumulative = 0.0
        points: list[EquityPoint] = []
        for point in sorted(replay.daily_pnl, key=lambda item: item.day):
            cumulative += point.net_pnl
            points.append(EquityPoint(day=point.day, cumulative_pnl=round(cumulative, 2)))
        series.append(EquitySeries(bot_id=bot.id, name=bot.name, strategy_profile=bot.strategy_profile, summary=replay.summary, points=points))
    return EquityComparisonResponse(
        symbol=normalized_symbol,
        timeframe="M5",
        period_days=days,
        updated_at_utc=datetime.now(timezone.utc),
        series=series,
        missing_bot_ids=missing,
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
    return SupabaseStore(settings).load_chart(bot, settings.chart_cache_limit, source_bot_id=_market_data_source_bot_id(bot))


@app.get("/api/bots/{bot_id}/historical-replay", response_model=HistoricalReplayResponse)
def read_historical_replay(bot_id: str, request: Request, days: int = 120) -> HistoricalReplayResponse:
    _require_api_session(request)
    if days < 1 or days > 365:
        raise HTTPException(status_code=422, detail="replay days must be between 1 and 365")
    bot = _find_bot(bot_id, include_archived=True)
    if not _uses_supabase_results():
        raise HTTPException(status_code=503, detail="historical replay requires DAYTRADE_RESULTS_STORE=SUPABASE")
    store = SupabaseStore(settings)
    source_bot_id = _market_data_source_bot_id(bot)
    cached = store.load_backtest_snapshot(bot.id, days)
    if cached is not None:
        cached.candles = store.load_candles(bot, settings.chart_cache_limit, source_bot_id=source_bot_id)
        return cached
    candles = store.load_candles(bot, settings.backtest_candle_limit, source_bot_id=source_bot_id)
    if not candles:
        raise HTTPException(status_code=404, detail="no historical candles available for replay")
    return run_historical_replay(bot, candles, settings, days=days)


@app.get("/api/results", response_model=ResultsResponse, deprecated=True)
def read_legacy_results(request: Request) -> ResultsResponse:
    _require_api_session(request)
    bots = _list_bots()
    if not bots:
        raise HTTPException(status_code=404, detail="no bots configured")
    return _load_bot_results(bots[0])


@app.post("/api/trades", status_code=204)
def ingest_trade(payload: TradeIngestRequest, x_2lotus_ingest_key: str | None = Header(default=None)) -> None:
    _require_ingest_key(x_2lotus_ingest_key)
    if not _uses_supabase_results():
        raise HTTPException(status_code=503, detail="trade ingestion requires DAYTRADE_RESULTS_STORE=SUPABASE")
    _find_bot(payload.bot_id)
    SupabaseStore(settings).upsert_trade(payload.bot_id, payload.trade)


@app.post("/api/candles", status_code=204)
def ingest_candles(payload: CandleIngestRequest, x_2lotus_ingest_key: str | None = Header(default=None)) -> None:
    _require_ingest_key(x_2lotus_ingest_key)
    if not _uses_supabase_results():
        raise HTTPException(status_code=503, detail="candle ingestion requires DAYTRADE_RESULTS_STORE=SUPABASE")
    bot = _find_bot(payload.bot_id)
    if bot.symbol != payload.symbol or bot.timeframe != payload.timeframe:
        raise HTTPException(status_code=422, detail="candle symbol or timeframe does not match bot configuration")
    SupabaseStore(settings).upsert_candles(payload.bot_id, payload.symbol, payload.timeframe, payload.candles)


@app.get("/health", response_model=HealthResponse)
def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok", service=settings.app_name, timestamp_utc=datetime.now(timezone.utc))


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
        "backtest_market_data_bot_id": settings.backtest_market_data_bot_id,
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
        "happy_gold_v2_stop_atr": settings.happy_gold_v2_stop_atr,
        "happy_gold_v2_target_r": settings.happy_gold_v2_target_r,
        "happy_gold_v2_max_holding_bars": settings.happy_gold_v2_max_holding_bars,
        "enable_live_decisions": settings.enable_live_decisions,
        "dashboard_auth_configured": settings.dashboard_auth_configured,
        "results_store": settings.results_store,
        "supabase_results_configured": settings.supabase_results_configured,
    }


@app.post("/decision", response_model=DecisionResponse)
def decision(payload: DecisionRequest, x_2lotus_ingest_key: str | None = Header(default=None)) -> DecisionResponse:
    _require_ingest_key(x_2lotus_ingest_key)
    store: SupabaseStore | None = None
    strategy_profile = settings.strategy_profile
    if payload.bot_id and _uses_supabase_results():
        bot = _find_bot(payload.bot_id)
        strategy_profile = bot.strategy_profile
        if bot.symbol != payload.symbol or bot.timeframe != payload.timeframe:
            raise HTTPException(status_code=422, detail="decision symbol or timeframe does not match bot configuration")
        store = SupabaseStore(settings)
        store.upsert_candles(payload.bot_id, payload.symbol, payload.timeframe, payload.candles)
        store.advance_paper_trades(payload.bot_id, payload.candles)
        if strategy_profile in {"multitimeframe_trend_pullback", "portfolio_6_7", "adaptive_portfolio_3_6_7", "happy_gold_zigzag_scalper", "happy_gold_zigzag_regime_confirmed", "happy_gold_zigzag_retest_atr", *WEIGHTED_PORTFOLIO_PROFILES}:
            payload.candles = store.load_candles(
                bot,
                4000 if strategy_profile in {"adaptive_portfolio_3_6_7", "happy_gold_zigzag_regime_confirmed", "happy_gold_zigzag_retest_atr"} or strategy_profile in WEIGHTED_PORTFOLIO_PROFILES else 1000,
                source_bot_id=_market_data_source_bot_id(bot),
            )
    strategy_settings = settings
    if payload.bot_id:
        strategy_settings = copy(settings)
        strategy_settings.default_symbol = payload.symbol
        strategy_settings.default_timeframe = payload.timeframe
        if strategy_profile == "adaptive_portfolio_3_6_7" and store:
            strategy_settings.adaptive_component_health = store.load_adaptive_component_health(payload.timestamp_utc)
        if strategy_profile in WEIGHTED_PORTFOLIO_PROFILES and store:
            strategy_settings.portfolio_risk_state = store.load_portfolio_risk_state(payload.bot_id, payload.timestamp_utc)
    response = evaluate_decision(payload, strategy_settings, strategy_profile)
    if payload.bot_id and store and response.metadata.get("candidate"):
        signal_key = store.record_strategy_candidate(payload, response)
        if signal_key:
            store.record_paper_trade(signal_key, payload, response, "technical")
            if response.metadata.get("flow_confirmed"):
                store.record_paper_trade(signal_key, payload, response, "flow_confirmed")
    if payload.bot_id and store and response.action.value in {"buy", "sell"}:
        validation_variant = "flow_confirmed" if strategy_profile == "fimath_ema20_flow" and settings.fimath_flow_policy == "required" else "technical"
        closed_count = store.closed_paper_trade_count(payload.bot_id, validation_variant)
        response.metadata["validation_variant"] = validation_variant
        response.metadata["closed_paper_trades"] = closed_count
        if closed_count < settings.fimath_min_closed_paper_trades:
            response.action = DecisionAction.HOLD
            response.reason = "shadow_minimum_not_reached"
            response.size = 0.0
    logger.info(
        "decision request_id=%s symbol=%s timeframe=%s action=%s reason=%s candidate=%s flow_status=%s book_z=%s tick_z=%s flow_score=%s",
        payload.request_id,
        payload.symbol,
        payload.timeframe,
        response.action.value,
        response.reason,
        response.metadata.get("candidate", False),
        response.metadata.get("flow_status"),
        response.metadata.get("book_z"),
        response.metadata.get("tick_z"),
        response.metadata.get("flow_score"),
    )
    return response
