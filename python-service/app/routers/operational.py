"""Runtime, account, liveness and observability endpoints."""

from collections.abc import Callable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..schemas import AccountDashboardResponse, HealthResponse, OperationsResponse


def create_operational_router(
    *,
    operations_handler: Callable[..., OperationsResponse],
    account_handler: Callable[..., AccountDashboardResponse],
    health_handler: Callable[..., HealthResponse],
    readiness_handler: Callable[..., JSONResponse],
    metrics_handler: Callable[..., dict[str, object]],
    config_handler: Callable[..., dict[str, str | int | float | bool]],
) -> APIRouter:
    router = APIRouter(tags=["operations"])

    @router.get("/api/operations", response_model=OperationsResponse)
    def read_operations(request: Request) -> OperationsResponse:
        return operations_handler(request)

    @router.get("/api/account", response_model=AccountDashboardResponse)
    def read_account(request: Request) -> AccountDashboardResponse:
        return account_handler(request)

    @router.get("/health", response_model=HealthResponse)
    def healthcheck() -> HealthResponse:
        return health_handler()

    @router.get("/ready")
    def readiness() -> JSONResponse:
        return readiness_handler()

    @router.get("/api/metrics")
    def read_metrics(request: Request) -> dict[str, object]:
        return metrics_handler(request)

    @router.get("/config")
    def read_config(request: Request) -> dict[str, str | int | float | bool]:
        return config_handler(request)

    return router
