from app.main import app


def test_portal_routes_are_registered_outside_openapi() -> None:
    expected = {
        ("/", "GET"),
        ("/login", "GET"),
        ("/login", "POST"),
        ("/logout", "POST"),
        ("/bots", "GET"),
        ("/compare", "GET"),
        ("/growth-simulator", "GET"),
        ("/history", "GET"),
        ("/operations", "GET"),
        ("/account", "GET"),
        ("/bots/{bot_id}", "GET"),
        ("/results", "GET"),
    }
    routes = list(app.routes)
    routes.extend(
        nested
        for route in app.routes
        for nested in getattr(getattr(route, "original_router", None), "routes", [])
    )
    registered = {
        (route.path, method)
        for route in routes
        if hasattr(route, "path")
        for method in getattr(route, "methods", set())
    }
    assert expected <= registered

    documented_paths = app.openapi()["paths"]
    assert all(path not in documented_paths for path, _method in expected)
