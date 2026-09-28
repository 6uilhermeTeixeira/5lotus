"""HTTP registration for replay and historical comparison endpoints."""

from collections.abc import Callable

from fastapi import APIRouter, Request

from ..schemas import BacktestMarketChartResponse, EquityComparisonResponse, HistoricalReplayResponse


def create_replay_router(
    *,
    equity_comparison: Callable[..., EquityComparisonResponse],
    market_chart: Callable[..., BacktestMarketChartResponse],
    historical_replay: Callable[..., HistoricalReplayResponse],
) -> APIRouter:
    router = APIRouter(tags=["replays"])

    @router.get("/api/equity-comparison", response_model=EquityComparisonResponse)
    def read_equity_comparison(
        request: Request,
        symbol: str = "XAUUSD",
        days: int = 365,
        mode: str = "normalized",
    ) -> EquityComparisonResponse:
        return equity_comparison(request, symbol, days, mode)

    @router.get("/api/backtest-market-chart", response_model=BacktestMarketChartResponse)
    def read_backtest_market_chart(
        request: Request,
        symbol: str = "XAUUSD",
        resolution: str = "5m",
        days: int = 30,
        mode: str = "normalized",
    ) -> BacktestMarketChartResponse:
        return market_chart(request, symbol, resolution, days, mode)

    @router.get("/api/bots/{bot_id}/historical-replay", response_model=HistoricalReplayResponse)
    def read_historical_replay(
        bot_id: str,
        request: Request,
        days: int = 120,
    ) -> HistoricalReplayResponse:
        return historical_replay(bot_id, request, days)

    return router
