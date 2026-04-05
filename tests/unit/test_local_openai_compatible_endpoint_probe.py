from urllib.error import URLError

from app.config import settings
from app.services.local_openai_compatible_endpoint_probe import (
    build_local_openai_compatible_endpoint_status,
)


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def read(self) -> bytes:
        import json

        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_local_openai_compatible_endpoint_probe_reports_ready_model(monkeypatch) -> None:
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


def test_local_openai_compatible_endpoint_probe_reports_missing_model(monkeypatch) -> None:
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


def test_local_openai_compatible_endpoint_probe_reports_unreachable_endpoint(monkeypatch) -> None:
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
