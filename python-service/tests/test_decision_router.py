from app.main import app


def test_decision_route_preserves_mt5_contract() -> None:
    routes = list(app.routes)
    routes.extend(
        nested
        for route in app.routes
        for nested in getattr(getattr(route, "original_router", None), "routes", [])
    )
    decision_routes = [route for route in routes if getattr(route, "path", None) == "/decision"]
    assert len(decision_routes) == 1
    assert decision_routes[0].status_code in {None, 200}

    operation = app.openapi()["paths"]["/decision"]["post"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/DecisionResponse")
    header_names = {parameter["name"] for parameter in operation.get("parameters", [])}
    assert "x-2lotus-ingest-key" in header_names
