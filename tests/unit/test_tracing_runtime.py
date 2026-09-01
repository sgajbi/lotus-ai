"""OpenTelemetry tracing behind a flag (issue #152)."""

from collections.abc import Iterator

from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pytest import MonkeyPatch, fixture, raises

from app.config import settings
from app.main import app
from app.services.tracing_runtime import (
    configure_tracing,
    force_flush_tracing,
    inject_trace_context,
    is_tracing_active,
    provider_attempt_span,
    record_provider_span_outcome,
    reset_tracing_for_tests,
)


@fixture(autouse=True)
def _reset_tracing() -> Iterator[None]:
    yield
    reset_tracing_for_tests()


def _enable(exporter: InMemorySpanExporter) -> None:
    settings.tracing_enabled = True
    configure_tracing(span_exporter=exporter)


def test_tracing_is_off_by_default_and_configures_to_noop() -> None:
    configure_tracing()
    assert is_tracing_active() is False
    with provider_attempt_span(provider_id="p", model_id="m", attempt=0) as span:
        assert span is None
    headers: dict[str, object] = {}
    inject_trace_context(headers)
    assert headers == {}


def test_enabling_without_an_endpoint_refuses_startup() -> None:
    settings.tracing_enabled = True
    settings.tracing_otlp_endpoint = None
    with raises(RuntimeError) as exc_info:
        configure_tracing()
    assert "LOTUS_AI_TRACING_OTLP_ENDPOINT" in str(exc_info.value)


def test_server_span_carries_route_status_and_inbound_traceparent() -> None:
    exporter = InMemorySpanExporter()
    _enable(exporter)

    client = TestClient(app)
    response = client.get(
        "/health/live",
        headers={"traceparent": "00-11111111111111111111111111111111-2222222222222222-01"},
    )
    assert response.status_code == 200

    force_flush_tracing()
    spans = exporter.get_finished_spans()
    server_spans = [span for span in spans if span.kind.name == "SERVER"]
    assert len(server_spans) == 1
    span = server_spans[0]
    assert span.name == "GET /health/live"
    assert span.attributes is not None
    assert span.attributes["http.route"] == "/health/live"
    assert span.attributes["http.response.status_code"] == 200
    assert "lotus_ai.correlation_id" in span.attributes
    # The gateway-propagated W3C trace continues through lotus-ai.
    assert format(span.context.trace_id, "032x") == "11111111111111111111111111111111"


def test_provider_attempt_span_records_identity_and_outcome() -> None:
    exporter = InMemorySpanExporter()
    _enable(exporter)

    with provider_attempt_span(provider_id="text.local", model_id="qwen3:8b", attempt=1) as span:
        record_provider_span_outcome(span, outcome="success")

    force_flush_tracing()
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    attributes = spans[0].attributes
    assert attributes is not None
    assert spans[0].name == "lotus_ai.provider.request"
    assert attributes["lotus_ai.provider_id"] == "text.local"
    assert attributes["lotus_ai.model_id"] == "qwen3:8b"
    assert attributes["lotus_ai.attempt"] == 1
    assert attributes["lotus_ai.outcome"] == "success"


def test_traceparent_is_injected_on_provider_egress(monkeypatch: MonkeyPatch) -> None:
    exporter = InMemorySpanExporter()
    _enable(exporter)

    captured_headers: dict[str, str] = {}

    class _Response:
        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"id": "resp_trace", "output_text": "OK"}'

    def _urlopen(request: object, timeout: float) -> _Response:
        captured_headers.update(
            {key.lower(): value for key, value in getattr(request, "headers", {}).items()}
        )
        return _Response()

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    from app.providers.openai_compatible_text_transport import post_openai_compatible_response

    with provider_attempt_span(provider_id="p", model_id="m", attempt=0):
        post_openai_compatible_response(
            api_base="http://localhost:1234/v1",
            api_key=None,
            payload={"model": "m"},
            timeout_seconds=1.0,
            serving_provider_id="text.local",
            require_api_key=False,
            retry_limit=0,
        )

    assert "traceparent" in captured_headers
