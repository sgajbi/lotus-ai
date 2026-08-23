from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(autouse=True)
def add_authenticated_caller_header_to_protected_posts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_post = TestClient.post
    original_get = TestClient.get

    def authenticated_post(
        self: TestClient,
        url: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        headers = dict(kwargs.get("headers") or {})
        if _is_protected_post_path(str(url)) and not _has_caller_header(headers):
            caller_app = _resolve_declared_caller_app(
                json_body=kwargs.get("json"),
                params=kwargs.get("params"),
            )
            if caller_app:
                headers["X-Caller-App"] = caller_app
                kwargs["headers"] = headers
        return original_post(self, url, *args, **kwargs)

    monkeypatch.setattr(TestClient, "post", authenticated_post)

    def authenticated_get(
        self: TestClient,
        url: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        headers = dict(kwargs.get("headers") or {})
        if str(url).startswith("/ai/audit") and not _has_caller_header(headers):
            headers["X-Caller-App"] = "lotus-platform"
            kwargs["headers"] = headers
        return original_get(self, url, *args, **kwargs)

    monkeypatch.setattr(TestClient, "get", authenticated_get)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as integration_client:
        yield integration_client


def _has_caller_header(headers: dict[str, str]) -> bool:
    return any(header_name.lower() == "x-caller-app" for header_name in headers)


def _is_protected_post_path(path: str) -> bool:
    return (
        path == "/ai/tasks/execute"
        or path == "/platform/retrieval/search"
        or path.endswith("/submit-async")
        or path == "/platform/prompts/control-actions"
        or path == "/platform/providers/control-plane-actions/reset"
        or path == "/platform/async/control-plane-actions/apply"
        or path == "/platform/async/jobs/submit"
        or path == "/platform/workflow-packs/execute"
        or path == "/platform/workflow-packs/execute-async"
        or path == "/platform/workflow-packs/control-actions"
        or path.endswith("/review-actions")
        or path.endswith("/retry-decisions")
        or path.endswith("/retry-executions")
        or path.endswith("/replay-decisions")
        or path.endswith("/replay-executions")
    )


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
