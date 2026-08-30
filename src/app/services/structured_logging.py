"""Structured JSON logging with correlation context (issue #152, slice 1).

One logging configuration for the whole service: JSON lines, a
contextvars-backed correlation id set by the correlation middleware, and a
hard field allowlist. The allowlist is the privacy boundary: prompt text,
generated output, payloads and secrets cannot appear in a log line by
construction, because unknown fields are dropped at format time.

Telemetry is the one deliberately fail-open surface in lotus-ai: a logging
failure must never block a request. Everything else in the service fails
closed; this module documents its own exception.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from app.config import settings

correlation_id_var: ContextVar[str | None] = ContextVar("lotus_ai_correlation_id", default=None)
correlation_source_var: ContextVar[str | None] = ContextVar(
    "lotus_ai_correlation_source", default=None
)

# The complete vocabulary a log line may carry. Adding a field is a reviewed
# change here plus the allowlist test - never an ad hoc `extra` that might
# smuggle content. Deliberately absent: anything that could hold prompt text,
# generated output, context payloads, headers, or credentials.
LOG_FIELD_ALLOWLIST = frozenset(
    {
        "timestamp",
        "level",
        "service",
        "event",
        "correlation_id",
        "correlation_source",
        "logger",
        "route",
        "method",
        "status_code",
        "duration_ms",
        "caller_app",
        "request_id",
        "tenant_id",
        "task_id",
        "error_code",
        "provider_id",
        "provider_mode",
        "model_id",
        "model_version",
        "model_catalogue_entry_id",
        "attempt",
        "attempt_limit",
        "outcome",
        "failure_class",
        "http_status",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "total_tokens",
    }
)

_RESERVED_RECORD_FIELDS = {"timestamp", "level", "service", "event", "correlation_id"}


class StructuredJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "service": settings.service_name,
            "logger": record.name,
            "event": record.getMessage(),
            "correlation_id": correlation_id_var.get(),
            "correlation_source": correlation_source_var.get(),
        }
        for key, value in record.__dict__.items():
            if key in LOG_FIELD_ALLOWLIST and key not in _RESERVED_RECORD_FIELDS:
                line[key] = value
        return json.dumps(line, sort_keys=True, default=str)


def configure_structured_logging() -> None:
    """Idempotently install the JSON handler on the app's logger tree."""

    root = logging.getLogger("app")
    if any(isinstance(handler.formatter, StructuredJsonFormatter) for handler in root.handlers):
        return
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(StructuredJsonFormatter())
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())
    root.propagate = False


def bind_correlation_context(*, correlation_id: str, source: str) -> None:
    correlation_id_var.set(correlation_id)
    correlation_source_var.set(source)


def log_event(logger: logging.Logger, event: str, /, **fields: Any) -> None:
    """Emit one structured line; unknown fields are dropped by the formatter.

    Never raises: telemetry is fail-open by design (the module docstring's
    documented exception to the service's fail-closed posture).
    """

    try:
        allowed = {key: value for key, value in fields.items() if key in LOG_FIELD_ALLOWLIST}
        logger.info(event, extra=allowed)
    except Exception:  # noqa: BLE001 - telemetry must never block a request
        pass
