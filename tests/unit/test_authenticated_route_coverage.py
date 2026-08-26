"""No product route is reachable without a verified caller identity.

Issue #149: `X-Caller-App` was a self-asserted header and 13 of 20 routers had no caller binding.
The fix routes every product router through `require_authenticated_caller`.

These tests assert the *behaviour* rather than the wiring. An earlier version walked `app.routes`
looking for the dependency object, which found nothing: this FastAPI version defers
`include_router` into `_IncludedRouter` wrappers, so the product routes are not flattened into
`app.routes` at all. That test failed while the application was correct - it was reading the
declaration instead of the effect.

Reading the effect also closes a gap the wiring check could not: it covers every path the service
publishes, so a router included directly rather than through `PROTECTED_ROUTER_BINDINGS` is caught
too. The inventory is no longer the thing being trusted.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import PROTECTED_ROUTER_BINDINGS, PUBLIC_UNAUTHENTICATED_PATHS, app

_HTTP_METHODS = ("get", "post", "put", "patch", "delete")

# A request that never carries caller identity must be refused. 401 and 403 are both acceptable
# refusals; anything else means the route answered, or failed for an unrelated reason.
_REFUSAL_STATUSES = frozenset({401, 403})


def _published_operations() -> list[tuple[str, str]]:
    """Every (method, path) the service publishes, from the OpenAPI document itself."""

    operations = [
        (method, path)
        for path, item in app.openapi().get("paths", {}).items()
        for method in _HTTP_METHODS
        if method in item
    ]
    assert operations, "No published operations found; this test would assert nothing."
    return operations


def test_every_published_non_public_operation_refuses_an_unidentified_caller() -> None:
    client = TestClient(app)

    answered = []
    for method, path in _published_operations():
        if path in PUBLIC_UNAUTHENTICATED_PATHS:
            continue
        # Path parameters are irrelevant: admission is refused before routing to a handler, so a
        # syntactically valid placeholder is enough and no fixture data is required.
        concrete = path.replace("{", "").replace("}", "")
        response = client.request(method.upper(), concrete)
        if response.status_code not in _REFUSAL_STATUSES:
            answered.append(f"{method.upper()} {path} -> {response.status_code}")

    assert answered == [], (
        "These published operations answered a caller with no verified identity, so they are "
        f"reachable without authentication: {answered}. See issue #149."
    )


def test_the_public_allowlist_is_reachable_without_caller_identity() -> None:
    """The allowlist must stay small and must actually work, or the check above is vacuous."""

    client = TestClient(app)

    assert PUBLIC_UNAUTHENTICATED_PATHS == {
        "/",
        "/health",
        "/health/live",
        "/health/ready",
        "/metadata",
        "/metrics",
    }

    unreachable = {
        path: client.get(path).status_code
        for path in sorted(PUBLIC_UNAUTHENTICATED_PATHS)
        if client.get(path).status_code != 200
    }
    assert unreachable == {}, f"Public paths did not answer: {unreachable}"


def test_every_product_router_is_bound_through_the_protected_inventory() -> None:
    """The inventory is not the security boundary, but an empty one would hide a regression."""

    names = [name for name, _router in PROTECTED_ROUTER_BINDINGS]

    assert len(names) == len(set(names)), f"Duplicate router bindings: {names}"
    assert len(names) >= 19, f"Protected router inventory shrank to {len(names)}: {names}"
    for name, router in PROTECTED_ROUTER_BINDINGS:
        assert router.routes, f"Protected router {name!r} contributes no routes."
