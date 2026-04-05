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


def test_openai_live_text_provider_parses_advisor_brief_structured_output(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_input_cost_per_1k_tokens = 0.01
    settings.live_text_output_cost_per_1k_tokens = 0.03

    monkeypatch.setattr(
        "app.providers.openai_live_text_provider._post_openai_response",
        lambda **_: {
            "id": "resp_advisor_123",
            "model": "gpt-5.4",
            "output_text": (
                '{"grounded_summary":"Portfolio lagged benchmark on YTD.",'
                '"talking_points":[{"headline":"Active Return was -6.68%.",'
                '"detail":"Benchmark underperformance was visible in the supplied facts.",'
                '"tone":"warning","evidence_refs":[{"metric_label":"Active Return",'
                '"metric_value":"-6.68%","source_ref":"lotus-gateway:workbench:'
                'PB_SG_GLOBAL_BAL_001:performance-summary:YTD"}]}],'
                '"recommended_actions":[{"label":"Review Attribution Drivers",'
                '"detail":"Open Attribution Detail before the client discussion.",'
                '"evidence_refs":[]}],"risks_and_exceptions":[]}'
            ),
            "usage": {"input_tokens": 220, "output_tokens": 80, "total_tokens": 300},
        },
    )

    response = OpenAILiveTextProvider().execute(
        _request(
                caller_app="lotus-gateway",
                context_payload={
                    "portfolio": {
                        "portfolio_id": "PB_SG_GLOBAL_BAL_001",
                        "display_label": "PB SG GLOBAL BAL 001",
                    },
                    "period": {"period": "YTD"},
                    "performance": {
                        "portfolio_return_pct": 1.25,
                    "benchmark_return_pct": 7.93,
                    "active_return_pct": -6.68,
                },
                "supportability": [{"label": "Return History", "value": "Ready"}],
            },
            source_refs=[
                "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD"
            ],
        )
    )

    assert response.provider_id == "text.openai"
    assert response.stubbed is False
    assert response.message == "Portfolio lagged benchmark on YTD."
    assert response.structured_output["grounded_summary"] == "Portfolio lagged benchmark on YTD."
    assert response.structured_output["talking_points"][0]["headline"] == "Active Return was -6.68%."
    assert response.structured_output["recommended_actions"][0]["label"] == (
        "Review Attribution Drivers"
    )


def test_openai_live_text_provider_parses_fenced_advisor_brief_json(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.live_text_model_id = "gpt-5.4"
    monkeypatch.setattr(
        "app.providers.openai_live_text_provider._post_openai_response",
        lambda **_: {
            "id": "resp_advisor_fenced",
            "model": "gpt-5.4",
            "output_text": (
                "```json\n"
                "{\n"
                "  \"grounded_summary\": \"Portfolio lagged benchmark on YTD.\",\n"
                "  \"talking_points\": [],\n"
                "  \"recommended_actions\": [],\n"
                "  \"risks_and_exceptions\": []\n"
                "}\n"
                "```"
            ),
            "usage": {"input_tokens": 220, "output_tokens": 80, "total_tokens": 300},
        },
    )

    response = OpenAILiveTextProvider().execute(
        _request(
                caller_app="lotus-gateway",
                context_payload={
                    "portfolio": {
                        "portfolio_id": "PB_SG_GLOBAL_BAL_001",
                        "display_label": "PB SG GLOBAL BAL 001",
                    },
                    "period": {"period": "YTD"},
                    "performance": {"active_return_pct": -6.68},
                "supportability": [{"label": "Advisor Brief", "value": "Ready"}],
            },
            source_refs=[
                "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD"
            ],
        )
    )

    assert response.structured_output["grounded_summary"] == "Portfolio lagged benchmark on YTD."
    assert response.structured_output["talking_points"] == []


def test_openai_live_text_provider_parses_advisor_json_with_trailing_text(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.live_text_model_id = "gpt-5.4"
    monkeypatch.setattr(
        "app.providers.openai_live_text_provider._post_openai_response",
        lambda **_: {
            "id": "resp_advisor_trailing_text",
            "model": "gpt-5.4",
            "output_text": (
                "{\"grounded_summary\":\"Portfolio lagged benchmark on YTD.\","
                "\"talking_points\":[],\"recommended_actions\":[],"
                "\"risks_and_exceptions\":[]}\n\nGenerated from supplied source refs."
            ),
            "usage": {"input_tokens": 220, "output_tokens": 80, "total_tokens": 300},
        },
    )

    response = OpenAILiveTextProvider().execute(
        _request(
                caller_app="lotus-gateway",
                context_payload={
                    "portfolio": {
                        "portfolio_id": "PB_SG_GLOBAL_BAL_001",
                        "display_label": "PB SG GLOBAL BAL 001",
                    },
                    "period": {"period": "YTD"},
                    "performance": {"active_return_pct": -6.68},
                "supportability": [{"label": "Advisor Brief", "value": "Ready"}],
            },
            source_refs=[
                "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD"
            ],
        )
    )

    assert response.structured_output["grounded_summary"] == "Portfolio lagged benchmark on YTD."
    assert response.structured_output["recommended_actions"] == []


def test_openai_live_text_provider_extracts_summary_from_truncated_advisor_json(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.live_text_model_id = "gpt-5.4"
    monkeypatch.setattr(
        "app.providers.openai_live_text_provider._post_openai_response",
        lambda **_: {
            "id": "resp_advisor_truncated",
            "model": "gpt-5.4",
            "output_text": (
                "{\"grounded_summary\":\"Portfolio lagged benchmark on YTD.\","
                "\"talking_points\":[{\"headline\":\"Portfolio trails benchmark YTD\""
            ),
            "usage": {"input_tokens": 220, "output_tokens": 80, "total_tokens": 300},
        },
    )

    response = OpenAILiveTextProvider().execute(
        _request(
                caller_app="lotus-gateway",
                context_payload={
                    "portfolio": {
                        "portfolio_id": "PB_SG_GLOBAL_BAL_001",
                        "display_label": "PB SG GLOBAL BAL 001",
                    },
                    "period": {"period": "YTD"},
                    "performance": {"active_return_pct": -6.68},
                "supportability": [{"label": "Advisor Brief", "value": "Ready"}],
            },
            source_refs=[
                "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD"
            ],
        )
    )

    assert response.structured_output["grounded_summary"] == "Portfolio lagged benchmark on YTD."
    assert response.structured_output["talking_points"] == []


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


def test_openai_live_text_provider_builds_advisor_output_contract_override() -> None:
    message = _build_user_message(
        _request(
            caller_app="lotus-gateway",
            context_payload={
                "portfolio": {"portfolio_id": "PB_SG_GLOBAL_BAL_001"},
                "period": {"period": "YTD"},
                "performance": {"active_return_pct": -6.68},
                "supportability": [{"label": "Advisor Brief", "value": "Ready"}],
            },
            source_refs=[
                "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD"
            ],
        )
    )

    assert "Return JSON only with keys grounded_summary" in message
    assert "Context Payload:" in message
    assert "portfolio.display_label" in message
    assert "benchmark.benchmark_name" in message
    assert "output_contract_override" not in message


def test_openai_live_text_provider_falls_back_when_advisor_summary_leaks_contract_text(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.live_text_model_id = "gpt-5.4"
    monkeypatch.setattr(
        "app.providers.openai_live_text_provider._post_openai_response",
        lambda **_: {
            "id": "resp_advisor_bad_summary",
            "model": "gpt-5.4",
            "output_text": (
                '{"grounded_summary":"The output contract for the structured Lotus domain with '
                'the provided data and context is as follows.",'
                '"talking_points":[],"recommended_actions":[],"risks_and_exceptions":[]}'
            ),
            "usage": {"input_tokens": 220, "output_tokens": 80, "total_tokens": 300},
        },
    )

    response = OpenAILiveTextProvider().execute(
        _request(
                caller_app="lotus-gateway",
                context_payload={
                    "portfolio": {
                        "portfolio_id": "PB_SG_GLOBAL_BAL_001",
                        "display_label": "PB SG GLOBAL BAL 001",
                    },
                    "period": {"period": "YTD"},
                    "performance": {
                        "portfolio_return_pct": 1.25,
                    "benchmark_return_pct": 7.93,
                    "active_return_pct": -6.68,
                },
                "supportability": [{"label": "Advisor Brief", "value": "Ready"}],
            },
            source_refs=[
                "lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD"
            ],
        )
    )

    assert response.message.startswith("PB SG GLOBAL BAL 001 delivered 1.25% over YTD")
    assert response.structured_output["advisor_brief_guardrail_triggered"] is True
    assert response.structured_output["advisor_brief_guardrail_reason"] == (
        "invalid_grounded_summary_language"
    )


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
