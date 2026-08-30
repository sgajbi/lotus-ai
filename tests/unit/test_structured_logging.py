"""Structured JSON logging foundation (issue #152, slice 1).

The allowlist is the privacy boundary: these tests pin that prompt text,
generated output and payload-bearing fields cannot reach a log line, that
correlation context rides every line, and that telemetry is fail-open.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from io import BytesIO
from email.message import Message
from urllib import error

import pytest

from app.config import settings
from app.services.structured_logging import (
    LOG_FIELD_ALLOWLIST,
    StructuredJsonFormatter,
    bind_correlation_context,
    configure_structured_logging,
    log_event,
)


class _CollectingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[dict[str, object]] = []
        self.setFormatter(StructuredJsonFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(json.loads(self.format(record)))


@pytest.fixture
def _collector() -> Iterator["_CollectingHandler"]:
    """Deterministic collection regardless of ambient suite state: snapshot the
    app logger tree, normalize it for the test, restore afterwards."""

    logger = logging.getLogger("app")
    snapshot = (list(logger.handlers), logger.level, logger.propagate)
    child_snapshots = {
        name: (child.level, child.propagate)
        for name in ("app.http", "app.provider", "app.errors", "app.test")
        for child in (logging.getLogger(name),)
    }
    ambient_disable = logging.root.manager.disable

    handler = _CollectingHandler()
    logging.disable(logging.NOTSET)
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.disabled = False
    for name in child_snapshots:
        child = logging.getLogger(name)
        child.setLevel(logging.NOTSET)
        child.propagate = True
        child.disabled = False
    yield handler
    logger.handlers, level, propagate = snapshot[0], snapshot[1], snapshot[2]
    logger.setLevel(level)
    logger.propagate = propagate
    for name, (child_level, child_propagate) in child_snapshots.items():
        child = logging.getLogger(name)
        child.setLevel(child_level)
        child.propagate = child_propagate
    logging.disable(ambient_disable)


def test_formatter_enforces_the_field_allowlist_and_correlation_context(
    _collector: _CollectingHandler,
) -> None:
    bind_correlation_context(correlation_id="corr-log-001", source="provided")
    log_event(
        logging.getLogger("app.test"),
        "unit_event",
        caller_app="lotus-manage",
        status_code=200,
        prompt="THE PROMPT MUST NEVER APPEAR",
        structured_output={"secret": "content"},
        authorization="Bearer nope",
    )

    assert len(_collector.lines) == 1
    line = _collector.lines[0]
    assert line["event"] == "unit_event"
    assert line["correlation_id"] == "corr-log-001"
    assert line["correlation_source"] == "provided"
    assert line["caller_app"] == "lotus-manage"
    assert line["status_code"] == 200
    serialized = json.dumps(line)
    assert "THE PROMPT MUST NEVER APPEAR" not in serialized
    assert "Bearer nope" not in serialized
    assert "secret" not in serialized


def test_allowlist_contains_no_content_bearing_field_names() -> None:
    forbidden = {
        "prompt",
        "output",
        "payload",
        "context",
        "structured_output",
        "message_body",
        "headers",
        "authorization",
        "api_key",
        "detail",
        "result",
    }
    assert not forbidden & LOG_FIELD_ALLOWLIST


def test_log_event_is_fail_open() -> None:
    class _ExplodingLogger:
        def info(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError("logging backend down")

    log_event(_ExplodingLogger(), "never_raises", status_code=500)  # type: ignore[arg-type]


def test_configure_is_idempotent_and_respects_the_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = logging.getLogger("app")
    snapshot = (list(logger.handlers), logger.level, logger.propagate)
    try:
        # Start from an explicitly unconfigured tree: the guarantee under test
        # is fresh-configure behavior plus idempotency of the second call.
        logger.handlers = []
        monkeypatch.setattr(settings, "log_level", "warning")
        configure_structured_logging()
        configure_structured_logging()
        structured = [
            handler
            for handler in logger.handlers
            if isinstance(handler.formatter, StructuredJsonFormatter)
        ]
        assert len(structured) == 1
        assert logger.level == logging.WARNING
    finally:
        logger.handlers = snapshot[0]
        logger.setLevel(snapshot[1])
        logger.propagate = snapshot[2]


def test_provider_attempts_share_the_correlation_id_across_retry_and_success(
    monkeypatch: pytest.MonkeyPatch, _collector: _CollectingHandler
) -> None:
    """The issue's evaluation condition: 429 then success under retry_limit=1
    produces two provider_attempt lines with the same correlation id, distinct
    attempt numbers, and the correlation id forwarded to the provider."""

    from app.providers.openai_compatible_text_transport import post_openai_compatible_response

    bind_correlation_context(correlation_id="corr-retry-777", source="provided")
    seen_headers: list[dict[str, str]] = []
    calls = {"count": 0}

    class _SuccessResponse:
        def __enter__(self) -> "_SuccessResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "output_text": "ok",
                    "usage": {"input_tokens": 11, "output_tokens": 7},
                }
            ).encode("utf-8")

    def _urlopen(request: object, timeout: float) -> object:
        seen_headers.append(dict(getattr(request, "headers", {})))
        calls["count"] += 1
        if calls["count"] == 1:
            raise error.HTTPError(
                url="https://api.openai.com/v1/responses",
                code=429,
                msg="Too Many Requests",
                hdrs=Message(),
                fp=BytesIO(b"{}"),
            )
        return _SuccessResponse()

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    payload = post_openai_compatible_response(
        api_base="https://api.openai.com/v1",
        api_key="secret",
        payload={"model": "gpt-5.4"},
        timeout_seconds=4.0,
        provider_display_name="text.openai",
        require_api_key=True,
        retry_limit=1,
    )

    assert payload["_lotus_retry_count"] == 1
    assert all(headers.get("X-correlation-id") == "corr-retry-777" for headers in seen_headers)

    attempts = [line for line in _collector.lines if line["event"] == "provider_attempt"]
    assert [line["attempt"] for line in attempts] == [0, 1]
    assert [line["outcome"] for line in attempts] == ["retry", "success"]
    assert attempts[0]["failure_class"] == "PROVIDER_RATE_LIMITED"
    assert attempts[0]["http_status"] == 429
    assert attempts[1]["input_tokens"] == 11
    assert attempts[1]["output_tokens"] == 7
    assert {line["correlation_id"] for line in attempts} == {"corr-retry-777"}
    assert all(line["model_id"] == "gpt-5.4" for line in attempts)
    serialized = json.dumps(attempts)
    assert "secret" not in serialized
