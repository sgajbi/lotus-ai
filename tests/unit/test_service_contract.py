from typing import Any, cast

from fastapi.testclient import TestClient
from starlette.routing import Match, Mount, Route

from app.main import SERVICE_NAME, _get_prometheus_route_name, _resolve_effective_route, app


def test_service_name_is_lotus_prefixed() -> None:
    assert SERVICE_NAME.startswith("lotus-")


def test_root_contract_includes_delivery_phase() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["phase"] == "foundation"


def test_prometheus_route_name_preserves_existing_name_when_matched_route_has_no_path() -> None:
    class _RouteWithoutPath:
        def matches(self, scope: dict[str, Any]) -> tuple[Match, dict[str, Any]]:
            return Match.FULL, {}

    route = _RouteWithoutPath()

    assert (
        _get_prometheus_route_name(cast(dict[str, Any], {}), cast(list[Route], [route]), "/parent")
        == "/parent"
    )


def test_prometheus_route_name_uses_partial_match_until_full_match() -> None:
    class _PartialRoute:
        path = "/partial"

        def matches(self, scope: dict[str, Any]) -> tuple[Match, dict[str, Any]]:
            return Match.PARTIAL, {}

    class _FullRoute:
        path = "/full"

        def matches(self, scope: dict[str, Any]) -> tuple[Match, dict[str, Any]]:
            return Match.FULL, {}

    routes = cast(list[Route], [_PartialRoute(), _FullRoute()])

    assert _get_prometheus_route_name(cast(dict[str, Any], {}), routes) == "/full"


def test_prometheus_route_name_resolves_nested_mounted_routes() -> None:
    def _endpoint() -> dict[str, str]:
        return {"status": "ok"}

    mounted = Mount("/mounted", routes=[Route("/child", endpoint=_endpoint)])
    scope = {
        "type": "http",
        "path": "/mounted/child",
        "root_path": "",
        "method": "GET",
        "headers": [],
    }

    assert _get_prometheus_route_name(scope, cast(list[Route], [mounted])) == "/mounted/child"


def test_prometheus_route_name_returns_none_when_mounted_child_does_not_match() -> None:
    def _endpoint() -> dict[str, str]:
        return {"status": "ok"}

    mounted = Mount("/mounted", routes=[Route("/other", endpoint=_endpoint)])
    scope = {
        "type": "http",
        "path": "/mounted/child",
        "root_path": "",
        "method": "GET",
        "headers": [],
    }

    assert _get_prometheus_route_name(scope, cast(list[Route], [mounted])) is None


def test_resolve_effective_route_handles_fastapi_match_failures_and_context_routes() -> None:
    class _FallbackRoute:
        path = "/fallback"

        def _match(self, scope: dict[str, Any]) -> tuple[None, dict[str, Any], None, object]:
            raise RuntimeError("match failed")

    fallback_route = cast(Route, _FallbackRoute())
    assert _resolve_effective_route(fallback_route, cast(dict[str, Any], {})) is fallback_route

    class _Context:
        starlette_route = object()

    class _ContextRoute:
        def _match(
            self, scope: dict[str, Any]
        ) -> tuple[None, dict[str, Any], None, type[_Context]]:
            return None, {}, None, _Context

    context_route = cast(Route, _ContextRoute())
    assert (
        _resolve_effective_route(context_route, cast(dict[str, Any], {}))
        is _Context.starlette_route
    )

    class _EmptyContext:
        starlette_route = None

    class _NoContextRoute:
        def _match(
            self, scope: dict[str, Any]
        ) -> tuple[None, dict[str, Any], None, type[_EmptyContext]]:
            return None, {}, None, _EmptyContext

    no_context_route = cast(Route, _NoContextRoute())
    assert _resolve_effective_route(no_context_route, cast(dict[str, Any], {})) is no_context_route
