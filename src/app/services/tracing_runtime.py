"""OpenTelemetry tracing behind a flag (issue #152, S4-slice).

Spans are hand-rolled at the two seams lotus-ai owns - the HTTP server
boundary and the provider transport attempt - rather than through framework
auto-instrumentation, so span names and attributes stay under this
repository's control and the no-content telemetry rule holds by
construction (bounded attributes only; never prompt or output text).

Naming, recorded for alignment with the lotus-core #569 programme:
- server spans: ``{METHOD} {route_template}`` (OTel HTTP semantic style)
- provider client spans: ``lotus_ai.provider.request``
- attributes beyond OTel semconv use the ``lotus_ai.`` namespace, mirroring
  the metric prefix.

The module holds its own ``TracerProvider`` instead of the process-global
one, so tests can configure and reset it freely; W3C ``traceparent`` is
extracted on ingress and injected on provider egress through the explicit
propagator API. Tracing is telemetry: once configured, failures never block
a request. Configuration itself is validated fail-closed - enabling tracing
without an endpoint (and without an injected exporter) refuses startup
rather than silently exporting nowhere.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from app.config import settings

_tracer_provider: TracerProvider | None = None
_propagator = TraceContextTextMapPropagator()


def configure_tracing(*, span_exporter: SpanExporter | None = None) -> None:
    """Configure the lotus-ai tracer provider from settings.

    ``span_exporter`` is the explicit injection seam (tests pass an
    in-memory exporter); by default the OTLP HTTP exporter targets
    ``LOTUS_AI_TRACING_OTLP_ENDPOINT``, which is required when tracing is
    enabled - enabling tracing that exports nowhere would be a silently
    broken control.
    """

    global _tracer_provider
    if not settings.tracing_enabled:
        _tracer_provider = None
        return
    exporter = span_exporter
    if exporter is None:
        if not settings.tracing_otlp_endpoint:
            raise RuntimeError(
                "LOTUS_AI_TRACING_OTLP_ENDPOINT is required when LOTUS_AI_TRACING_ENABLED=true."
            )
        exporter = OTLPSpanExporter(endpoint=settings.tracing_otlp_endpoint)
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": settings.service_name,
                "service.version": settings.service_version,
            }
        )
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    _tracer_provider = provider


def force_flush_tracing() -> None:
    """Flush buffered spans (batch export is asynchronous by design)."""

    if _tracer_provider is not None:
        _tracer_provider.force_flush()


def reset_tracing_for_tests() -> None:
    global _tracer_provider
    if _tracer_provider is not None:
        _tracer_provider.shutdown()
    _tracer_provider = None


def is_tracing_active() -> bool:
    return _tracer_provider is not None


def _tracer() -> trace.Tracer | None:
    if _tracer_provider is None:
        return None
    return _tracer_provider.get_tracer("lotus-ai")


@contextmanager
def server_request_span(
    *,
    method: str,
    headers: dict[str, str],
    correlation_id: str | None,
) -> Iterator["_ServerSpanHandle"]:
    """One server span per HTTP request; a no-op handle when tracing is off."""

    tracer = _tracer()
    if tracer is None:
        yield _ServerSpanHandle(span=None)
        return
    parent = _propagator.extract(carrier=headers)
    token = otel_context.attach(parent)
    span = tracer.start_span(method, context=parent, kind=trace.SpanKind.SERVER)
    handle = _ServerSpanHandle(span=span)
    try:
        with trace.use_span(span, end_on_exit=False):
            span.set_attribute("http.request.method", method)
            if correlation_id is not None:
                span.set_attribute("lotus_ai.correlation_id", correlation_id)
            yield handle
    finally:
        span.end()
        otel_context.detach(token)


class _ServerSpanHandle:
    def __init__(self, *, span: trace.Span | None) -> None:
        self._span = span

    def finish(self, *, method: str, route: str, status_code: int) -> None:
        if self._span is None:
            return
        self._span.update_name(f"{method} {route}")
        self._span.set_attribute("http.route", route)
        self._span.set_attribute("http.response.status_code", status_code)


@contextmanager
def provider_attempt_span(
    *,
    provider_id: str,
    model_id: str | None,
    attempt: int,
) -> Iterator[trace.Span | None]:
    """One client span per provider attempt; no-op when tracing is off."""

    tracer = _tracer()
    if tracer is None:
        yield None
        return
    with tracer.start_as_current_span(
        "lotus_ai.provider.request", kind=trace.SpanKind.CLIENT
    ) as span:
        span.set_attribute("lotus_ai.provider_id", provider_id)
        span.set_attribute("lotus_ai.model_id", model_id or "unknown")
        span.set_attribute("lotus_ai.attempt", attempt)
        yield span


def record_provider_span_outcome(span: trace.Span | None, *, outcome: str) -> None:
    if span is None:
        return
    span.set_attribute("lotus_ai.outcome", outcome)


def inject_trace_context(headers: dict[str, Any]) -> None:
    """Inject W3C traceparent into egress headers when a span is recording."""

    if _tracer_provider is None:
        return
    _propagator.inject(carrier=headers)
