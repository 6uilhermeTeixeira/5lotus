"""HTTP registration for authenticated market and trade ingestion."""

from collections.abc import Callable

from fastapi import APIRouter, Header, Request

from ..schemas import CandleIngestRequest, TickIngestRequest, TradeIngestRequest


def create_ingestion_router(
    *,
    ingest_trade_handler: Callable[..., None],
    ingest_candles_handler: Callable[..., None],
    ingest_ticks_handler: Callable[..., None],
) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["ingestion"])

    @router.post("/trades", status_code=204)
    def ingest_trade(
        payload: TradeIngestRequest,
        request: Request,
        x_2lotus_ingest_key: str | None = Header(default=None),
    ) -> None:
        return ingest_trade_handler(payload, request, x_2lotus_ingest_key)

    @router.post("/candles", status_code=204)
    def ingest_candles(
        payload: CandleIngestRequest,
        request: Request,
        x_2lotus_ingest_key: str | None = Header(default=None),
    ) -> None:
        return ingest_candles_handler(payload, request, x_2lotus_ingest_key)

    @router.post("/ticks", status_code=204)
    def ingest_ticks(
        payload: TickIngestRequest,
        request: Request,
        x_2lotus_ingest_key: str | None = Header(default=None),
    ) -> None:
        return ingest_ticks_handler(payload, request, x_2lotus_ingest_key)

    return router
