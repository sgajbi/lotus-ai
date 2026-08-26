from collections.abc import Iterator
from typing import Any
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from app.main import PUBLIC_UNAUTHENTICATED_PATHS, app


@pytest.fixture(autouse=True)
def add_authenticated_caller_header_to_protected_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_request = TestClient.request

    def authenticated_request(
        self: TestClient,
        method: str,
        url: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        headers = dict(kwargs.get("headers") or {})
        path = urlsplit(str(url)).path
        if path not in PUBLIC_UNAUTHENTICATED_PATHS and not _has_caller_header(headers):
            caller_app = (
                None
                if method.upper() in {"GET", "HEAD"}
                else _resolve_declared_caller_app(
                    json_body=kwargs.get("json"),
                    params=kwargs.get("params"),
                )
            )
            headers["X-Caller-App"] = caller_app or "lotus-platform"
            kwargs["headers"] = headers
        return original_request(self, method, url, *args, **kwargs)

    monkeypatch.setattr(TestClient, "request", authenticated_request)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as integration_client:
        yield integration_client


def _has_caller_header(headers: dict[str, str]) -> bool:
    return any(header_name.lower() == "x-caller-app" for header_name in headers)


def _resolve_declared_caller_app(
    *,
    json_body: object,
    params: object,
) -> str | None:
    if isinstance(params, dict):
        caller_app_param = params.get("caller_app")
        if isinstance(caller_app_param, str):
            return caller_app_param
    if not isinstance(json_body, dict):
        return None
    caller_app = json_body.get("caller_app")
    if isinstance(caller_app, str):
        return caller_app
    caller = json_body.get("caller")
    if isinstance(caller, dict):
        caller_app_value = caller.get("caller_app")
        if isinstance(caller_app_value, str):
            return caller_app_value
    task_request = json_body.get("task_request")
    if isinstance(task_request, dict):
        task_caller = task_request.get("caller")
        if isinstance(task_caller, dict):
            task_caller_app = task_caller.get("caller_app")
            if isinstance(task_caller_app, str):
                return task_caller_app
    return None
