from email.message import Message
from io import BytesIO
from urllib import error

from pytest import MonkeyPatch

from app.config import settings
from app.contracts.providers import ProviderFailureCategory
from app.providers.base import ProviderExecutionError
from app.providers.openai_live_text_provider import (
    OpenAILiveTextProvider,
    _build_user_message,
    _extract_output_text,
    _extract_usage,
    _post_openai_response,
)
from tests.unit.test_provider_gateway import _request


def test_openai_live_text_provider_returns_usage_and_cost(monkeypatch: MonkeyPatch) -> None:
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_input_cost_per_1k_tokens = 0.01
    settings.live_text_output_cost_per_1k_tokens = 0.03

    monkeypatch.setattr(
        "app.providers.openai_live_text_provider._post_openai_response",
        lambda **_: {
            "id": "resp_123",
            "model": "gpt-5.4",
            "output_text": "Live provider explanation.",
            "usage": {"input_tokens": 200, "output_tokens": 50, "total_tokens": 250},
        },
    )

    response = OpenAILiveTextProvider().execute(_request())

    assert response.provider_id == "text.openai"
    assert response.provider_mode == "openai"
    assert response.stubbed is False
    assert response.model_id == "gpt-5.4"
    assert response.provider_request_id == "resp_123"
    assert response.input_tokens == 200
    assert response.output_tokens == 50
    assert response.total_tokens == 250
    assert response.estimated_cost_usd == 0.0035
    assert response.message == "Live provider explanation."


def test_openai_live_text_provider_requires_api_key() -> None:
    settings.live_text_provider_api_key = None

    try:
        OpenAILiveTextProvider().execute(_request())
    except ProviderExecutionError as exc:
        assert exc.category == ProviderFailureCategory.INVALID_LIVE_CONFIGURATION
    else:
        raise AssertionError(
            "Expected ProviderExecutionError for missing live-provider credentials"
        )


def test_openai_live_text_provider_builds_user_message_with_context() -> None:
    message = _build_user_message(_request())

    assert '"task_id": "explain.v1"' in message
    assert '"caller_app": "lotus-manage"' in message
    assert '"rule_count": 3' in message


def test_openai_live_text_provider_extracts_text_from_output_fragments() -> None:
    text = _extract_output_text(
        {
            "output": [
                {
                    "content": [
                        {"text": "First line"},
                        {"text": "Second line"},
                    ]
                }
            ]
        }
    )

    assert text == "First line\nSecond line"


def test_openai_live_text_provider_rejects_missing_output_text() -> None:
    try:
        _extract_output_text({"output": [{"content": [{}]}]})
    except ProviderExecutionError as exc:
        assert exc.category == ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR
    else:
        raise AssertionError("Expected ProviderExecutionError for missing provider output text")


def test_openai_live_text_provider_extracts_usage_when_missing() -> None:
    assert _extract_usage({}) == (None, None, None)


def test_openai_live_text_provider_maps_rate_limit_errors(monkeypatch: MonkeyPatch) -> None:
    def _raise_http_error(*args: object, **kwargs: object) -> object:
        raise error.HTTPError(
            url="https://api.openai.com/v1/responses",
            code=429,
            msg="Too Many Requests",
            hdrs=Message(),
            fp=BytesIO(b'{"error": {"message": "Rate limit hit"}}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", _raise_http_error)

    try:
        _post_openai_response(
            api_base="https://api.openai.com/v1",
            api_key="secret",
            payload={"model": "gpt-5.4"},
            timeout_seconds=4.0,
        )
    except ProviderExecutionError as exc:
        assert exc.category == ProviderFailureCategory.PROVIDER_RATE_LIMITED
        assert exc.message == "Rate limit hit"
    else:
        raise AssertionError("Expected ProviderExecutionError for rate-limited provider response")


def test_openai_live_text_provider_maps_upstream_http_errors(monkeypatch: MonkeyPatch) -> None:
    def _raise_http_error(*args: object, **kwargs: object) -> object:
        raise error.HTTPError(
            url="https://api.openai.com/v1/responses",
            code=500,
            msg="Server Error",
            hdrs=Message(),
            fp=BytesIO(b'{"error": {"message": "Transient upstream failure"}}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", _raise_http_error)

    try:
        _post_openai_response(
            api_base="https://api.openai.com/v1",
            api_key="secret",
            payload={"model": "gpt-5.4"},
            timeout_seconds=4.0,
        )
    except ProviderExecutionError as exc:
        assert exc.category == ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR
        assert exc.message == "Transient upstream failure"
    else:
        raise AssertionError("Expected ProviderExecutionError for upstream provider response")


def test_openai_live_text_provider_maps_timeout_errors(monkeypatch: MonkeyPatch) -> None:
    def _raise_timeout(*args: object, **kwargs: object) -> object:
        raise TimeoutError()

    monkeypatch.setattr("urllib.request.urlopen", _raise_timeout)

    try:
        _post_openai_response(
            api_base="https://api.openai.com/v1",
            api_key="secret",
            payload={"model": "gpt-5.4"},
            timeout_seconds=4.0,
        )
    except ProviderExecutionError as exc:
        assert exc.category == ProviderFailureCategory.PROVIDER_TIMEOUT
    else:
        raise AssertionError("Expected ProviderExecutionError for provider timeout")


def test_openai_live_text_provider_maps_url_errors(monkeypatch: MonkeyPatch) -> None:
    def _raise_url_error(*args: object, **kwargs: object) -> object:
        raise error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", _raise_url_error)

    try:
        _post_openai_response(
            api_base="https://api.openai.com/v1",
            api_key="secret",
            payload={"model": "gpt-5.4"},
            timeout_seconds=4.0,
        )
    except ProviderExecutionError as exc:
        assert exc.category == ProviderFailureCategory.PROVIDER_TIMEOUT
        assert "connection refused" in exc.message
    else:
        raise AssertionError("Expected ProviderExecutionError for provider URL error")


def test_openai_live_text_provider_posts_successfully_through_urlopen(
    monkeypatch: MonkeyPatch,
) -> None:
    class _Response:
        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"id": "resp_ok", "output_text": "OK"}'

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: _Response())

    payload = _post_openai_response(
        api_base="https://api.openai.com/v1",
        api_key="secret",
        payload={"model": "gpt-5.4"},
        timeout_seconds=4.0,
    )

    assert payload["id"] == "resp_ok"


def test_openai_live_text_provider_handles_non_json_error_bodies(monkeypatch: MonkeyPatch) -> None:
    def _raise_http_error(*args: object, **kwargs: object) -> object:
        raise error.HTTPError(
            url="https://api.openai.com/v1/responses",
            code=500,
            msg="Server Error",
            hdrs=Message(),
            fp=BytesIO(b"not json"),
        )

    monkeypatch.setattr("urllib.request.urlopen", _raise_http_error)

    try:
        _post_openai_response(
            api_base="https://api.openai.com/v1",
            api_key="secret",
            payload={"model": "gpt-5.4"},
            timeout_seconds=4.0,
        )
    except ProviderExecutionError as exc:
        assert exc.category == ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR
        assert exc.message == "OpenAI provider request failed."
    else:
        raise AssertionError("Expected ProviderExecutionError for invalid JSON error body")


def test_openai_live_text_provider_ignores_non_text_output_parts() -> None:
    text = _extract_output_text(
        {
            "output": [
                "invalid",
                {"content": "invalid"},
                {"content": ["invalid", {"text": "Recovered text"}]},
            ]
        }
    )

    assert text == "Recovered text"
