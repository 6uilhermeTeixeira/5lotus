"""Registration for the MT5 decision endpoint."""

from collections.abc import Callable

from fastapi import APIRouter, Header, Request

from ..schemas import DecisionRequest, DecisionResponse


def create_decision_router(*, decision_handler: Callable[..., DecisionResponse]) -> APIRouter:
    router = APIRouter(tags=["decision"])

    @router.post("/decision", response_model=DecisionResponse)
    def decision(
        payload: DecisionRequest,
        request: Request,
        x_2lotus_ingest_key: str | None = Header(default=None),
    ) -> DecisionResponse:
        return decision_handler(payload, request, x_2lotus_ingest_key)

    return router
