from app.main import app


def test_replay_routes_are_registered_and_documented() -> None:
    expected = {
        "/api/equity-comparison",
        "/api/backtest-market-chart",
        "/api/bots/{bot_id}/historical-replay",
    }
    routes = list(app.routes)
    routes.extend(
        nested
        for route in app.routes
        for nested in getattr(getattr(route, "original_router", None), "routes", [])
    )
    registered = {route.path for route in routes if hasattr(route, "path")}
    assert expected <= registered
    assert expected <= set(app.openapi()["paths"])
