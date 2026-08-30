"""HTTP-boundary and problem-response log lines (issue #152, slice 1)."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.services.structured_logging import StructuredJsonFormatter


class _CollectingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[dict[str, object]] = []
        self.setFormatter(StructuredJsonFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(json.loads(self.format(record)))


@pytest.fixture
def _collector() -> Iterator["_CollectingHandler"]:
    handler = _CollectingHandler()
    logger = logging.getLogger("app")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    yield handler
    logger.removeHandler(handler)


def _lines(handler: _CollectingHandler, event: str) -> list[dict[str, object]]:
    return [line for line in handler.lines if line["event"] == event]


def test_every_request_emits_one_boundary_line_with_correlation(
    client: TestClient, _collector: _CollectingHandler
) -> None:
    response = client.get("/metadata", headers={"X-Correlation-Id": "corr-http-123"})
    assert response.status_code == 200

    boundary = _lines(_collector, "http_request")
    assert len(boundary) == 1
    line = boundary[0]
    assert line["correlation_id"] == "corr-http-123"
    assert line["correlation_source"] == "provided"
    assert line["route"] == "/metadata"
    assert line["method"] == "GET"
    assert line["status_code"] == 200
    assert isinstance(line["duration_ms"], float)


def test_missing_correlation_header_is_generated_and_marked(
    client: TestClient, _collector: _CollectingHandler
) -> None:
    response = client.get("/metadata")
    assert response.status_code == 200

    line = _lines(_collector, "http_request")[0]
    assert line["correlation_source"] == "generated"
    assert line["correlation_id"]
    assert line["correlation_id"] == response.headers["X-Correlation-Id"]


def test_problem_responses_emit_an_error_line_with_the_bounded_code(
    client: TestClient, _collector: _CollectingHandler
) -> None:
    response = client.get(
        "/platform/observability/breakdowns",
        headers={"X-Caller-App": "lotus-unknown-app", "X-Correlation-Id": "corr-err-9"},
    )
    assert response.status_code == 403

    errors = _lines(_collector, "problem_response")
    assert len(errors) == 1
    line = errors[0]
    assert line["status_code"] == 403
    assert line["error_code"]
    assert line["correlation_id"] == "corr-err-9"
    assert line["caller_app"] == "lotus-unknown-app"


def test_metrics_endpoint_exposes_the_provider_vocabulary(client: TestClient) -> None:
    body = client.get("/metrics").text
    assert "lotus_ai_provider_requests_total" in body
    assert "lotus_ai_provider_latency_seconds" in body
    assert "lotus_ai_surface_supportability_state" in body
