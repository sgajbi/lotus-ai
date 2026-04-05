from __future__ import annotations

from email.message import Message
from types import TracebackType
from urllib import error
from urllib.error import URLError

from pytest import MonkeyPatch

from app.config import settings
from app.services.local_openai_compatible_endpoint_probe import (
    build_local_openai_compatible_endpoint_status,
    reset_local_openai_compatible_endpoint_probe_cache,
)


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def read(self) -> bytes:
        import json

        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None


def test_local_openai_compatible_endpoint_probe_reports_ready_model(
    monkeypatch: MonkeyPatch,
) -> None:
    reset_local_openai_compatible_endpoint_probe_cache()
    settings.live_text_api_base = "http://ollama:11434/v1"
    settings.live_text_model_id = "qwen3:8b"

    monkeypatch.setattr(
        "app.services.local_openai_compatible_endpoint_probe.urllib_request.urlopen",
        lambda request, timeout: _FakeResponse({"data": [{"id": "qwen3:8b"}]}),
    )

    status = build_local_openai_compatible_endpoint_status()

    assert status.endpoint_reachable is True
    assert status.model_available is True
    assert status.blocking_reason is None


def test_local_openai_compatible_endpoint_probe_reports_missing_model(
    monkeypatch: MonkeyPatch,
) -> None:
    reset_local_openai_compatible_endpoint_probe_cache()
    settings.live_text_api_base = "http://ollama:11434/v1"
    settings.live_text_model_id = "qwen3:8b"

    monkeypatch.setattr(
        "app.services.local_openai_compatible_endpoint_probe.urllib_request.urlopen",
        lambda request, timeout: _FakeResponse({"data": [{"id": "llama3.1:8b"}]}),
    )

    status = build_local_openai_compatible_endpoint_status()

    assert status.endpoint_reachable is True
    assert status.model_available is False
    assert "not advertised" in (status.blocking_reason or "")


def test_local_openai_compatible_endpoint_probe_reports_unreachable_endpoint(
    monkeypatch: MonkeyPatch,
) -> None:
    reset_local_openai_compatible_endpoint_probe_cache()
    settings.live_text_api_base = "http://ollama:11434/v1"
    settings.live_text_model_id = "qwen3:8b"

    monkeypatch.setattr(
        "app.services.local_openai_compatible_endpoint_probe.urllib_request.urlopen",
        lambda request, timeout: (_ for _ in ()).throw(URLError("connection refused")),
    )

    status = build_local_openai_compatible_endpoint_status()

    assert status.endpoint_reachable is False
    assert status.model_available is False
    assert "not reachable" in (status.blocking_reason or "")


def test_local_openai_compatible_endpoint_probe_requires_configured_model() -> None:
    reset_local_openai_compatible_endpoint_probe_cache()
    settings.live_text_api_base = "http://ollama:11434/v1"
    settings.live_text_model_id = None

    status = build_local_openai_compatible_endpoint_status()

    assert status.endpoint_reachable is False
    assert status.model_available is False
    assert "requires a configured model id" in (status.blocking_reason or "").lower()


def test_local_openai_compatible_endpoint_probe_reports_timeout(
    monkeypatch: MonkeyPatch,
) -> None:
    reset_local_openai_compatible_endpoint_probe_cache()
    settings.live_text_api_base = "http://ollama:11434/v1"
    settings.live_text_model_id = "qwen3:8b"

    monkeypatch.setattr(
        "app.services.local_openai_compatible_endpoint_probe.urllib_request.urlopen",
        lambda request, timeout: (_ for _ in ()).throw(TimeoutError()),
    )

    status = build_local_openai_compatible_endpoint_status()

    assert status.endpoint_reachable is False
    assert status.model_available is False
    assert "timed out" in (status.blocking_reason or "").lower()


def test_local_openai_compatible_endpoint_probe_reports_http_failure(
    monkeypatch: MonkeyPatch,
) -> None:
    reset_local_openai_compatible_endpoint_probe_cache()
    settings.live_text_api_base = "http://ollama:11434/v1"
    settings.live_text_model_id = "qwen3:8b"

    def _raise_http_error(request: object, timeout: float) -> object:
        raise error.HTTPError(
            url="http://ollama:11434/v1/models",
            code=503,
            msg="Service Unavailable",
            hdrs=Message(),
            fp=None,
        )

    monkeypatch.setattr(
        "app.services.local_openai_compatible_endpoint_probe.urllib_request.urlopen",
        _raise_http_error,
    )

    status = build_local_openai_compatible_endpoint_status()

    assert status.endpoint_reachable is False
    assert status.model_available is False
    assert "http 503" in (status.blocking_reason or "").lower()


def test_local_openai_compatible_endpoint_probe_reports_unreadable_catalog(
    monkeypatch: MonkeyPatch,
) -> None:
    reset_local_openai_compatible_endpoint_probe_cache()
    settings.live_text_api_base = "http://ollama:11434/v1"
    settings.live_text_model_id = "qwen3:8b"

    class _UnreadableResponse(_FakeResponse):
        def read(self) -> bytes:
            return b"{"

    monkeypatch.setattr(
        "app.services.local_openai_compatible_endpoint_probe.urllib_request.urlopen",
        lambda request, timeout: _UnreadableResponse({"data": []}),
    )

    status = build_local_openai_compatible_endpoint_status()

    assert status.endpoint_reachable is True
    assert status.model_available is False
    assert "unreadable model catalog" in (status.blocking_reason or "").lower()


def test_local_openai_compatible_endpoint_probe_reports_invalid_catalog_shape(
    monkeypatch: MonkeyPatch,
) -> None:
    reset_local_openai_compatible_endpoint_probe_cache()
    settings.live_text_api_base = "http://ollama:11434/v1"
    settings.live_text_model_id = "qwen3:8b"

    monkeypatch.setattr(
        "app.services.local_openai_compatible_endpoint_probe.urllib_request.urlopen",
        lambda request, timeout: _FakeResponse({"data": [{"id": ""}]}),
    )

    status = build_local_openai_compatible_endpoint_status()

    assert status.endpoint_reachable is True
    assert status.model_available is False
    assert "valid `/models` catalog" in (status.blocking_reason or "")


def test_local_openai_compatible_endpoint_probe_reuses_cached_result(
    monkeypatch: MonkeyPatch,
) -> None:
    reset_local_openai_compatible_endpoint_probe_cache()
    settings.live_text_api_base = "http://ollama:11434/v1"
    settings.live_text_model_id = "qwen3:8b"
    settings.live_text_local_probe_cache_seconds = 60
    call_count = 0

    def _urlopen(request: object, timeout: float) -> _FakeResponse:
        nonlocal call_count
        call_count += 1
        return _FakeResponse({"data": [{"id": "qwen3:8b"}]})

    monkeypatch.setattr(
        "app.services.local_openai_compatible_endpoint_probe.urllib_request.urlopen",
        _urlopen,
    )

    first = build_local_openai_compatible_endpoint_status()
    second = build_local_openai_compatible_endpoint_status()

    assert first.model_available is True
    assert second.model_available is True
    assert call_count == 1
