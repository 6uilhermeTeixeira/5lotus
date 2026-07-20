import logging
from hmac import compare_digest
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .auth import SESSION_COOKIE_NAME, create_session_value, has_valid_session, password_matches, read_login_password
from .config import get_settings
from .pages import render_catalog_page, render_login_page, render_results_page
from .results_store import get_bot, load_bots_catalog, load_results_snapshot, resolve_bot_results_file
from .schemas import BotCatalogItem, CandleIngestRequest, DecisionRequest, DecisionResponse, HealthResponse, MarketChartResponse, ResultsResponse, TradeIngestRequest
from .strategy import evaluate_decision
from .supabase_store import SupabaseStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

logger = logging.getLogger("2lotus.strategy")
settings = get_settings()
app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parent.parent / "public"), name="static")


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


def _find_bot(bot_id: str) -> BotCatalogItem:
    bot = next((item for item in _list_bots() if item.id == bot_id), None)
    if bot is None:
        raise HTTPException(status_code=404, detail="bot not found")
    return bot


def _uses_supabase_results() -> bool:
    return settings.results_store == "SUPABASE"


def _list_bots() -> list[BotCatalogItem]:
    return SupabaseStore(settings).list_bots() if _uses_supabase_results() else load_bots_catalog(settings.bots_catalog_path)


def _load_bot_results(bot: BotCatalogItem) -> ResultsResponse:
    if _uses_supabase_results():
        return SupabaseStore(settings).load_results(bot.id)
    return load_results_snapshot(resolve_bot_results_file(settings.bots_catalog_path, bot))


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
    return render_catalog_page(_list_bots())


@app.get("/bots/{bot_id}", response_class=HTMLResponse, response_model=None, include_in_schema=False)
def bot_results_page(bot_id: str, request: Request) -> HTMLResponse | RedirectResponse:
    if redirect := _require_page_session(request):
        return redirect
    return render_results_page(_find_bot(bot_id))


@app.get("/results", include_in_schema=False)
def legacy_results(request: Request) -> RedirectResponse:
    if redirect := _require_page_session(request):
        return redirect
    bots = _list_bots()
    return RedirectResponse(url=f"/bots/{bots[0].id}" if bots else "/bots", status_code=303)


@app.get("/api/bots", response_model=list[BotCatalogItem])
def read_bots(request: Request) -> list[BotCatalogItem]:
    _require_api_session(request)
    return _list_bots()


@app.get("/api/bots/{bot_id}/results", response_model=ResultsResponse)
def read_bot_results(bot_id: str, request: Request) -> ResultsResponse:
    _require_api_session(request)
    return _load_bot_results(_find_bot(bot_id))


@app.get("/api/bots/{bot_id}/chart", response_model=MarketChartResponse)
def read_bot_chart(bot_id: str, request: Request) -> MarketChartResponse:
    _require_api_session(request)
    bot = _find_bot(bot_id)
    if not _uses_supabase_results():
        raise HTTPException(status_code=503, detail="chart data requires DAYTRADE_RESULTS_STORE=SUPABASE")
    return SupabaseStore(settings).load_chart(bot, settings.chart_cache_limit)


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
        "fimath_partial_pct": settings.fimath_partial_pct,
        "chart_cache_limit": settings.chart_cache_limit,
        "enable_live_decisions": settings.enable_live_decisions,
        "dashboard_auth_configured": settings.dashboard_auth_configured,
        "results_store": settings.results_store,
        "supabase_results_configured": settings.supabase_results_configured,
    }


@app.post("/decision", response_model=DecisionResponse)
def decision(payload: DecisionRequest, x_2lotus_ingest_key: str | None = Header(default=None)) -> DecisionResponse:
    _require_ingest_key(x_2lotus_ingest_key)
    store: SupabaseStore | None = None
    if payload.bot_id and _uses_supabase_results():
        bot = _find_bot(payload.bot_id)
        if bot.symbol != payload.symbol or bot.timeframe != payload.timeframe:
            raise HTTPException(status_code=422, detail="decision symbol or timeframe does not match bot configuration")
        store = SupabaseStore(settings)
        store.upsert_candles(payload.bot_id, payload.symbol, payload.timeframe, payload.candles)
        store.advance_paper_trades(payload.bot_id, payload.candles)
    response = evaluate_decision(payload, settings)
    if payload.bot_id and store and response.action.value in {"buy", "sell"} and store.closed_paper_trade_count(payload.bot_id) < 30:
        response.action = response.action.HOLD
        response.reason = "fimath_shadow_minimum_not_reached"
        response.size = 0.0
    if payload.bot_id and _uses_supabase_results() and response.reason == "fimath_shadow_signal":
        SupabaseStore(settings).record_shadow_signal(payload, response)
    logger.info("decision request_id=%s symbol=%s timeframe=%s action=%s reason=%s", payload.request_id, payload.symbol, payload.timeframe, response.action.value, response.reason)
    return response
