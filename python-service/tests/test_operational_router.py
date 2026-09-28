from app.main import app


def test_operational_routes_are_registered_with_contract_models() -> None:
    expected = {
        "/api/operations",
        "/api/account",
        "/health",
        "/ready",
        "/api/metrics",
        "/config",
    }
    routes = list(app.routes)
    routes.extend(
        nested
        for route in app.routes
        for nested in getattr(getattr(route, "original_router", None), "routes", [])
    )
    registered = {route.path for route in routes if hasattr(route, "path")}
    assert expected <= registered
    documented_paths = set(app.openapi()["paths"])
    assert expected <= documented_paths

    assert app.openapi()["paths"]["/health"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/HealthResponse")
    assert app.openapi()["paths"]["/api/operations"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/OperationsResponse")
