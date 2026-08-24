from __future__ import annotations

import json
from typing import Any, cast

from fastapi import HTTPException
from starlette.requests import Request
from fastapi.testclient import TestClient
from _pytest.monkeypatch import MonkeyPatch

from app.config import settings
from app.main import app
from app.middleware.http_boundary import current_http_boundary_posture, _validate_request_size
from app.services.workflow_pack_run_ledger import WorkflowPackRunStoreUnavailableError


def _valid_task_request(correlation_id: str = "corr-error-test") -> dict[str, object]:
    return {
        "task_id": "explain.v1",
        "input_mode": "STRUCTURED_CONTEXT",
        "caller": {
            "caller_app": "lotus-manage",
            "correlation_id": correlation_id,
            "tenant_id": "tenant-sg-001",
        },
        "context": {
            "summary": "Explain bounded posture",
            "payload": {"status": "BLOCKED"},
            "source_refs": [],
        },
        "expected_output_label": "EXPLANATION_ONLY",
    }


def _valid_retrieval_request(correlation_id: str = "corr-retrieval-error") -> dict[str, object]:
    return {
        "query": "shared ai platform service",
        "caller_app": "lotus-manage",
        "correlation_id": correlation_id,
        "tenant_id": "tenant-sg-001",
        "source_ids": ["lotus-platform-rfcs"],
        "limit": 3,
    }


def _assert_problem_response(
    response: Any,
    *,
    status_code: int,
    error_code: str,
    correlation_id: str,
) -> dict[str, Any]:
    assert response.status_code == status_code
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["X-Correlation-Id"] == correlation_id
    body = cast(dict[str, Any], response.json())
    assert body["status"] == status_code
    assert body["error_code"] == error_code
    assert body["correlation_id"] == correlation_id
    assert body["type"].startswith("https://lotus.ai/problems/")
    assert isinstance(body["detail"], str)
    return body


def test_http_boundary_adds_secure_headers_and_cors_for_allowed_origin(
    client: TestClient,
) -> None:
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:3000", "X-Correlation-Id": "corr-boundary-ok"},
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-Id"] == "corr-boundary-ok"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"


def test_http_boundary_rejects_disallowed_host_with_problem_response(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "http_allowed_hosts", "api.lotus.local")

    response = client.get(
        "/health",
        headers={"Host": "evil.example", "X-Correlation-Id": "corr-host-reject"},
    )

    body = _assert_problem_response(
        response,
        status_code=400,
        error_code="LOTUS_AI_HOST_NOT_ALLOWED",
        correlation_id="corr-host-reject",
    )
    assert body["metadata"] == {"boundary_control": "trusted_host"}


def test_http_boundary_rejects_disallowed_cors_preflight_with_problem_response(
    client: TestClient,
) -> None:
    response = client.options(
        "/ai/tasks/execute",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "POST",
            "X-Correlation-Id": "corr-cors-reject",
        },
    )

    _assert_problem_response(
        response,
        status_code=403,
        error_code="LOTUS_AI_CORS_ORIGIN_FORBIDDEN",
        correlation_id="corr-cors-reject",
    )


def test_http_boundary_rejects_oversized_request_before_handler(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "http_max_request_body_bytes", 16)

    response = client.post(
        "/ai/tasks/execute",
        json=_valid_task_request("corr-too-large"),
        headers={"X-Correlation-Id": "corr-too-large"},
    )

    body = _assert_problem_response(
        response,
        status_code=413,
        error_code="LOTUS_AI_REQUEST_TOO_LARGE",
        correlation_id="corr-too-large",
    )
    assert body["metadata"]["boundary_control"] == "request_size"
    assert body["metadata"]["max_request_body_bytes"] == 16


def test_http_boundary_rejects_invalid_content_length_with_problem_response() -> None:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/health",
            "headers": [
                (b"content-length", b"not-a-number"),
                (b"x-correlation-id", b"corr-invalid-length"),
            ],
        }
    )

    response = _validate_request_size(request, current_http_boundary_posture())

    assert response is not None
    assert response.status_code == 400
    assert response.media_type == "application/problem+json"
    body = json.loads(bytes(response.body))
    assert body["error_code"] == "LOTUS_AI_INVALID_CONTENT_LENGTH"
    assert body["correlation_id"] == "corr-invalid-length"
    assert body["metadata"] == {"boundary_control": "request_size"}


def test_http_boundary_allows_preflight_for_allowed_origin(client: TestClient) -> None:
    response = client.options(
        "/ai/tasks/execute",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "X-Correlation-Id": "corr-cors-ok",
        },
    )

    assert response.status_code == 204
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
    assert response.headers["Access-Control-Allow-Methods"]


def test_http_boundary_can_disable_secure_headers_and_enable_wildcard_cors(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "http_secure_headers_enabled", False)
    monkeypatch.setattr(settings, "http_cors_allowed_origins", "*")
    monkeypatch.setattr(settings, "http_cors_allow_credentials", True)

    response = client.get(
        "/health",
        headers={"Origin": "https://desk.lotus.example", "X-Correlation-Id": "corr-cors-any"},
    )

    assert response.status_code == 200
    assert "X-Frame-Options" not in response.headers
    assert response.headers["Access-Control-Allow-Origin"] == "*"
    assert response.headers["Access-Control-Allow-Credentials"] == "true"


def test_http_boundary_adds_hsts_when_enabled(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "http_hsts_enabled", True)
    monkeypatch.setattr(settings, "http_hsts_max_age_seconds", 123)

    response = client.get(
        "/health",
        headers={"X-Correlation-Id": "corr-hsts"},
    )

    assert response.status_code == 200
    assert response.headers["Strict-Transport-Security"] == "max-age=123; includeSubDomains"


def test_validation_error_uses_problem_details_and_correlation(client: TestClient) -> None:
    response = client.post(
        "/ai/tasks/execute",
        json={},
        headers={"X-Correlation-Id": "corr-validation", "X-Caller-App": "lotus-manage"},
    )

    body = _assert_problem_response(
        response,
        status_code=422,
        error_code="LOTUS_AI_VALIDATION_FAILED",
        correlation_id="corr-validation",
    )
    assert body["metadata"]["validation_error_count"] >= 1


def test_not_found_error_uses_stable_problem_code(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "local_header_caller_identity_enabled", True)
    response = client.get(
        "/ai/audit/not-found",
        headers={"X-Correlation-Id": "corr-audit-missing"},
    )

    _assert_problem_response(
        response,
        status_code=404,
        error_code="LOTUS_AI_AUDIT_RECORD_NOT_FOUND",
        correlation_id="corr-audit-missing",
    )


def test_conflict_error_uses_problem_details(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    def raise_conflict(_request: object) -> None:
        raise HTTPException(status_code=409, detail="Retrieval execution is disabled.")

    monkeypatch.setattr("app.routers.retrieval.search_sources", raise_conflict)
    response = client.post(
        "/platform/retrieval/search",
        json=_valid_retrieval_request("corr-conflict"),
        headers={"X-Correlation-Id": "corr-conflict"},
    )

    _assert_problem_response(
        response,
        status_code=409,
        error_code="LOTUS_AI_CONFLICT",
        correlation_id="corr-conflict",
    )


def test_rate_limit_error_uses_problem_details(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    def raise_rate_limit(_request: object) -> None:
        raise HTTPException(
            status_code=429, detail="Workflow-pack async queue capacity is saturated."
        )

    monkeypatch.setattr("app.routers.retrieval.search_sources", raise_rate_limit)

    response = client.post(
        "/platform/retrieval/search",
        json=_valid_retrieval_request("corr-rate-limit"),
        headers={"X-Correlation-Id": "corr-rate-limit"},
    )

    _assert_problem_response(
        response,
        status_code=429,
        error_code="LOTUS_AI_QUEUE_CAPACITY_EXCEEDED",
        correlation_id="corr-rate-limit",
    )


def test_store_unavailable_error_uses_problem_details(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    def raise_store_unavailable(_request: object) -> None:
        raise WorkflowPackRunStoreUnavailableError("Workflow-pack run store is not ready.")

    monkeypatch.setattr("app.routers.tasks.execute_task", raise_store_unavailable)

    response = client.post(
        "/ai/tasks/execute",
        json=_valid_task_request("corr-store-unavailable"),
        headers={"X-Correlation-Id": "corr-store-unavailable"},
    )

    _assert_problem_response(
        response,
        status_code=503,
        error_code="LOTUS_AI_RUNTIME_STORE_UNAVAILABLE",
        correlation_id="corr-store-unavailable",
    )


def test_http_exception_dict_detail_preserves_explicit_problem_metadata(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    def raise_explicit_problem(_request: object) -> None:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "Bounded queue policy conflict.",
                "error_code": "LOTUS_AI_EXPLICIT_CONFLICT",
                "metadata": {"policy_id": "queue-policy.advisor-brief.v1"},
            },
        )

    monkeypatch.setattr("app.routers.retrieval.search_sources", raise_explicit_problem)

    response = client.post(
        "/platform/retrieval/search",
        json=_valid_retrieval_request("corr-explicit-problem"),
        headers={"X-Correlation-Id": "corr-explicit-problem"},
    )

    body = _assert_problem_response(
        response,
        status_code=409,
        error_code="LOTUS_AI_EXPLICIT_CONFLICT",
        correlation_id="corr-explicit-problem",
    )
    assert body["detail"] == "Bounded queue policy conflict."
    assert body["metadata"] == {"policy_id": "queue-policy.advisor-brief.v1"}


def test_http_exception_unknown_status_uses_http_error_code(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    def raise_unknown_status(_request: object) -> None:
        raise HTTPException(status_code=418, detail="Short and stout.")

    monkeypatch.setattr("app.routers.retrieval.search_sources", raise_unknown_status)

    response = client.post(
        "/platform/retrieval/search",
        json=_valid_retrieval_request("corr-teapot"),
        headers={"X-Correlation-Id": "corr-teapot"},
    )

    body = _assert_problem_response(
        response,
        status_code=418,
        error_code="LOTUS_AI_HTTP_ERROR",
        correlation_id="corr-teapot",
    )
    assert body["title"] == "I'm a Teapot"


def test_http_exception_nonstandard_status_uses_generic_title(
    client: TestClient, monkeypatch: MonkeyPatch
) -> None:
    def raise_nonstandard_status(_request: object) -> None:
        raise HTTPException(status_code=599, detail="Gateway extension failure.")

    monkeypatch.setattr("app.routers.retrieval.search_sources", raise_nonstandard_status)

    response = client.post(
        "/platform/retrieval/search",
        json=_valid_retrieval_request("corr-nonstandard-status"),
        headers={"X-Correlation-Id": "corr-nonstandard-status"},
    )

    body = _assert_problem_response(
        response,
        status_code=599,
        error_code="LOTUS_AI_HTTP_ERROR",
        correlation_id="corr-nonstandard-status",
    )
    assert body["title"] == "HTTP error"


def test_unexpected_error_is_sanitized_with_problem_details(
    monkeypatch: MonkeyPatch,
) -> None:
    def raise_unexpected(_request: object) -> None:
        raise RuntimeError("secret upstream payload should not leak")

    monkeypatch.setattr("app.routers.tasks.execute_task", raise_unexpected)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/ai/tasks/execute",
            json=_valid_task_request("corr-unexpected"),
            headers={"X-Correlation-Id": "corr-unexpected"},
        )

    body = _assert_problem_response(
        response,
        status_code=500,
        error_code="LOTUS_AI_INTERNAL_ERROR",
        correlation_id="corr-unexpected",
    )
    assert "secret upstream payload" not in body["detail"]
