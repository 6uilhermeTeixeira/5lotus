from app.main import app


def test_ingestion_routes_preserve_contract() -> None:
    expected = {"/api/trades", "/api/candles", "/api/ticks"}
    routes = list(app.routes)
    routes.extend(
        nested
        for route in app.routes
        for nested in getattr(getattr(route, "original_router", None), "routes", [])
    )
    ingestion = {
        route.path: route
        for route in routes
        if getattr(route, "path", None) in expected
    }
    assert set(ingestion) == expected
    assert all(route.status_code == 204 for route in ingestion.values())
    assert expected <= set(app.openapi()["paths"])

    for path in expected:
        operation = app.openapi()["paths"][path]["post"]
        header_names = {parameter["name"] for parameter in operation.get("parameters", [])}
        assert "x-2lotus-ingest-key" in header_names
