from email.message import Message
from io import BytesIO
from typing import Any, cast
from urllib import error

from pytest import MonkeyPatch

from app.config import settings
from app.contracts.providers import ProviderFailureCategory
from app.providers.base import ProviderExecutionError
from app.providers.openai_compatible_text_transport import (
    build_structured_output,
    build_user_message,
    extract_balanced_json_object,
    extract_output_text,
    extract_usage,
    parse_json_object,
    strip_json_code_fence,
)
from app.providers.local_openai_compatible_text_provider import LocalOpenAICompatibleTextProvider
from app.providers.openai_live_text_provider import OpenAILiveTextProvider, _post_openai_response
from tests.unit.test_provider_gateway import _request


class _OpenAICompatibleResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> "_OpenAICompatibleResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


def test_openai_live_text_provider_returns_usage_and_cost(monkeypatch: MonkeyPatch) -> None:
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_model_version = "2026-06-01"
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
    assert response.model_version == "2026-06-01"
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
            source_refs=["lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD"],
        )
    )
    structured_output = cast(dict[str, Any], response.structured_output)

    assert response.provider_id == "text.openai"
    assert response.stubbed is False
    assert response.message == "Portfolio lagged benchmark on YTD."
    assert structured_output["grounded_summary"] == "Portfolio lagged benchmark on YTD."
    assert (
        cast(list[dict[str, Any]], structured_output["talking_points"])[0]["headline"]
        == "Active Return was -6.68%."
    )
    assert cast(list[dict[str, Any]], structured_output["recommended_actions"])[0]["label"] == (
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
                '  "grounded_summary": "Portfolio lagged benchmark on YTD.",\n'
                '  "talking_points": [],\n'
                '  "recommended_actions": [],\n'
                '  "risks_and_exceptions": []\n'
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
            source_refs=["lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD"],
        )
    )

    structured_output = cast(dict[str, Any], response.structured_output)
    assert structured_output["grounded_summary"] == "Portfolio lagged benchmark on YTD."
    assert structured_output["talking_points"] == []


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
                '{"grounded_summary":"Portfolio lagged benchmark on YTD.",'
                '"talking_points":[],"recommended_actions":[],'
                '"risks_and_exceptions":[]}\n\nGenerated from supplied source refs.'
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
            source_refs=["lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD"],
        )
    )

    structured_output = cast(dict[str, Any], response.structured_output)
    assert structured_output["grounded_summary"] == "Portfolio lagged benchmark on YTD."
    assert structured_output["recommended_actions"] == []


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
                '{"grounded_summary":"Portfolio lagged benchmark on YTD.",'
                '"talking_points":[{"headline":"Portfolio trails benchmark YTD"'
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
            source_refs=["lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD"],
        )
    )

    structured_output = cast(dict[str, Any], response.structured_output)
    assert structured_output["grounded_summary"] == "Portfolio lagged benchmark on YTD."
    assert structured_output["talking_points"] == []


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
    message = build_user_message(_request())

    assert '"task_id": "explain.v1"' in message
    assert '"caller_app": "lotus-manage"' in message
    assert '"rule_count": 3' in message


def test_openai_live_text_provider_builds_advisor_output_contract_override() -> None:
    message = build_user_message(
        _request(
            caller_app="lotus-gateway",
            context_payload={
                "portfolio": {"portfolio_id": "PB_SG_GLOBAL_BAL_001"},
                "period": {"period": "YTD"},
                "performance": {"active_return_pct": -6.68},
                "supportability": [{"label": "Advisor Brief", "value": "Ready"}],
            },
            source_refs=["lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD"],
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
            source_refs=["lotus-gateway:workbench:PB_SG_GLOBAL_BAL_001:performance-summary:YTD"],
        )
    )

    assert response.message.startswith("PB SG GLOBAL BAL 001 delivered 1.25% over YTD")
    structured_output = cast(dict[str, Any], response.structured_output)
    assert structured_output["advisor_brief_guardrail_triggered"] is True
    assert structured_output["advisor_brief_guardrail_reason"] == (
        "invalid_grounded_summary_language"
    )


def test_openai_live_text_provider_extracts_text_from_output_fragments() -> None:
    text = extract_output_text(
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
        extract_output_text({"output": [{"content": [{}]}]})
    except ProviderExecutionError as exc:
        assert exc.category == ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR
    else:
        raise AssertionError("Expected ProviderExecutionError for missing provider output text")


def test_openai_live_text_provider_extracts_usage_when_missing() -> None:
    assert extract_usage({}) == (None, None, None)


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
        assert exc.message == "OpenAI provider rate limit exceeded."
        assert "Rate limit hit" not in exc.message
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
        assert exc.message == "OpenAI provider request failed at the upstream provider boundary."
        assert "Transient upstream failure" not in exc.message
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
        assert exc.message == (
            "OpenAI provider request did not complete within the configured timeout."
        )
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
        assert exc.message == (
            "OpenAI provider request did not complete within the configured timeout."
        )
        assert "connection refused" not in exc.message
    else:
        raise AssertionError("Expected ProviderExecutionError for provider URL error")


def test_openai_live_text_provider_posts_successfully_through_urlopen(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: _OpenAICompatibleResponse(
            b'{"id": "resp_ok", "output_text": "OK"}'
        ),
    )

    payload = _post_openai_response(
        api_base="https://api.openai.com/v1",
        api_key="secret",
        payload={"model": "gpt-5.4"},
        timeout_seconds=4.0,
    )

    payload_dict = cast(dict[str, Any], payload)
    assert payload_dict["id"] == "resp_ok"
    assert payload_dict["_lotus_retry_count"] == 0


def test_openai_live_text_provider_retries_managed_transient_failure_then_success(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.live_text_provider_api_key = "secret"
    attempts = {"count": 0}

    def _urlopen(*args: object, **kwargs: object) -> object:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise error.HTTPError(
                url="https://api.openai.com/v1/responses",
                code=503,
                msg="Service Unavailable",
                hdrs=Message(),
                fp=BytesIO(b'{"error": {"message": "raw upstream detail should not leak"}}'),
            )
        return _OpenAICompatibleResponse(
            b'{"id": "resp_retry_ok", "model": "gpt-5.4", "output_text": "OK"}'
        )

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    response = OpenAILiveTextProvider().execute(_request(retry_limit=2))

    assert attempts["count"] == 2
    assert response.retry_count == 1
    assert response.provider_request_id == "resp_retry_ok"
    assert response.structured_output["retry_count"] == 1


def test_openai_compatible_transport_retries_local_transient_failure_then_success(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.live_text_model_id = "qwen3:8b"
    attempts = {"count": 0}

    def _urlopen(*args: object, **kwargs: object) -> object:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise TimeoutError()
        return _OpenAICompatibleResponse(b'{"id": "resp_local_retry_ok", "output_text": "OK"}')

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    response = LocalOpenAICompatibleTextProvider().execute(_request(retry_limit=1))

    assert attempts["count"] == 2
    assert response.retry_count == 1
    assert response.provider_request_id == "resp_local_retry_ok"
    assert response.structured_output["retry_count"] == 1


def test_openai_compatible_transport_preserves_category_when_retries_exhaust(
    monkeypatch: MonkeyPatch,
) -> None:
    attempts = {"count": 0}

    def _urlopen(*args: object, **kwargs: object) -> object:
        attempts["count"] += 1
        raise error.HTTPError(
            url="https://api.openai.com/v1/responses",
            code=429,
            msg="Too Many Requests",
            hdrs=Message(),
            fp=BytesIO(b'{"error": {"message": "raw account detail should not leak"}}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    try:
        _post_openai_response(
            api_base="https://api.openai.com/v1",
            api_key="secret",
            payload={"model": "gpt-5.4"},
            timeout_seconds=4.0,
            retry_limit=2,
        )
    except ProviderExecutionError as exc:
        assert attempts["count"] == 3
        assert exc.category == ProviderFailureCategory.PROVIDER_RATE_LIMITED
        assert exc.message == "OpenAI provider rate limit exceeded."
        assert "raw account detail" not in exc.message
    else:
        raise AssertionError("Expected ProviderExecutionError after exhausted retries")


def test_openai_compatible_transport_retries_url_error_before_timeout_failure(
    monkeypatch: MonkeyPatch,
) -> None:
    attempts = {"count": 0}

    def _urlopen(*args: object, **kwargs: object) -> object:
        attempts["count"] += 1
        raise error.URLError("temporary resolver failure")

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    try:
        _post_openai_response(
            api_base="https://api.openai.com/v1",
            api_key="secret",
            payload={"model": "gpt-5.4"},
            timeout_seconds=4.0,
            retry_limit=1,
        )
    except ProviderExecutionError as exc:
        assert attempts["count"] == 2
        assert exc.category == ProviderFailureCategory.PROVIDER_TIMEOUT
    else:
        raise AssertionError("Expected ProviderExecutionError after retried URL error")


def test_openai_compatible_transport_does_not_retry_invalid_configuration(
    monkeypatch: MonkeyPatch,
) -> None:
    attempts = {"count": 0}

    def _urlopen(*args: object, **kwargs: object) -> object:
        attempts["count"] += 1
        return _OpenAICompatibleResponse(b'{"id": "unexpected"}')

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)

    try:
        _post_openai_response(
            api_base="https://api.openai.com/v1",
            api_key=None,
            payload={"model": "gpt-5.4"},
            timeout_seconds=4.0,
            retry_limit=2,
        )
    except ProviderExecutionError as exc:
        assert attempts["count"] == 0
        assert exc.category == ProviderFailureCategory.INVALID_LIVE_CONFIGURATION
    else:
        raise AssertionError("Expected ProviderExecutionError for missing credentials")


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
        assert exc.message == "OpenAI provider request failed at the upstream provider boundary."
    else:
        raise AssertionError("Expected ProviderExecutionError for invalid JSON error body")


def test_openai_live_text_provider_ignores_non_text_output_parts() -> None:
    text = extract_output_text(
        {
            "output": [
                "invalid",
                {"content": "invalid"},
                {"content": ["invalid", {"text": "Recovered text"}]},
            ]
        }
    )

    assert text == "Recovered text"


def test_openai_compatible_transport_builds_plain_json_user_message_for_non_advisor_payload() -> (
    None
):
    message = build_user_message(
        _request(
            context_payload={"rule_count": 3},
            source_refs=["lotus-manage:run:rebalance"],
        )
    )

    assert '"rule_count": 3' in message
    assert "Return JSON only with keys grounded_summary" not in message


def test_openai_compatible_transport_returns_plain_structured_output_for_non_advisor_payload() -> (
    None
):
    response_message, structured_output = build_structured_output(
        descriptor=OpenAILiveTextProvider().descriptor,
        request=_request(context_payload={"rule_count": 3}, source_refs=["lotus-manage:run:001"]),
        response_payload={
            "id": "resp_plain",
            "model": "gpt-5.4",
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        },
        output_message="Plain explanation.",
    )

    assert response_message == "Plain explanation."
    assert structured_output["provider_id"] == "text.openai"
    assert structured_output["source_refs"] == ["lotus-manage:run:001"]
    assert "grounded_summary" not in structured_output


def test_openai_compatible_transport_parses_non_dict_json_as_none() -> None:
    assert parse_json_object('["not", "an", "object"]') is None
    assert parse_json_object("prefix with no braces") is None
    assert parse_json_object('prefix {"broken": } suffix') is None


def test_openai_compatible_transport_strips_generic_code_fence() -> None:
    assert strip_json_code_fence('```\n{"a":1}\n```') == '{"a":1}'


def test_openai_compatible_transport_extracts_balanced_json_with_escaped_quotes() -> None:
    value = (
        'prefix {"grounded_summary":"He said \\"stay disciplined\\".","talking_points":[]} suffix'
    )

    extracted = extract_balanced_json_object(value)

    assert extracted == (
        '{"grounded_summary":"He said \\"stay disciplined\\".","talking_points":[]}'
    )
