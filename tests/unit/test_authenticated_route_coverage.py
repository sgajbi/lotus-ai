from fastapi.testclient import TestClient
from fastapi.routing import APIRoute

from app.http.authenticated_caller import require_authenticated_caller
from app.main import PROTECTED_ROUTER_BINDINGS, PUBLIC_UNAUTHENTICATED_PATHS, app


_EXPECTED_PROTECTED_ROUTERS = {
    "access_control",
    "artifacts",
    "async_runtime",
    "audit",
    "capabilities",
    "capability_packs",
    "evals",
    "observability",
    "platform",
    "prompts",
    "provider_retention_confirmations",
    "providers",
    "retrieval",
    "safety",
    "task_runtime",
    "tasks",
    "use_cases",
    "workflow_packs",
    "workflow_run_attestations",
}


def test_every_included_product_router_is_in_the_protected_inventory() -> None:
    assert {name for name, _router in PROTECTED_ROUTER_BINDINGS} == _EXPECTED_PROTECTED_ROUTERS


def test_every_product_route_requires_authenticated_caller() -> None:
    application_routes = [route for route in app.routes if isinstance(route, APIRoute)]
    unprotected: set[tuple[str, str, frozenset[str]]] = set()
    for name, router in PROTECTED_ROUTER_BINDINGS:
        assert router.routes, f"protected router {name!r} has no routes"
        for router_route in router.routes:
            assert isinstance(router_route, APIRoute)
            route_identity = _route_identity(router_route)
            included_routes = [
                route for route in application_routes if _route_identity(route) == route_identity
            ]
            assert len(included_routes) == 1, (
                f"protected router {name!r} route {route_identity!r} must be included exactly once"
            )
            application_route = included_routes[0]
            if not any(
                dependency.dependency is require_authenticated_caller
                for dependency in application_route.dependencies
            ):
                unprotected.add(route_identity)

    assert unprotected == set()


def _route_identity(route: APIRoute) -> tuple[str, str, frozenset[str]]:
    """Return the stable identity preserved when FastAPI includes a router."""

    return (route.path, route.name, frozenset(route.methods or set()))


def test_product_route_rejects_missing_caller_identity() -> None:
    response = TestClient(app).get("/platform/capabilities")

    assert response.status_code == 403


def test_public_route_allowlist_remains_available_without_caller_identity() -> None:
    client = TestClient(app)

    assert PUBLIC_UNAUTHENTICATED_PATHS == {
        "/",
        "/health",
        "/health/live",
        "/health/ready",
        "/metadata",
        "/metrics",
    }
    responses = {path: client.get(path) for path in PUBLIC_UNAUTHENTICATED_PATHS}

    assert responses.keys() == PUBLIC_UNAUTHENTICATED_PATHS
    assert {path: response.status_code for path, response in responses.items()} == {
        path: 200 for path in PUBLIC_UNAUTHENTICATED_PATHS
    }
