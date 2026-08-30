from pytest import MonkeyPatch

from app.config import settings
from app.contracts.providers import ProviderFailureCategory
from app.providers.base import ProviderExecutionError
from app.providers.local_openai_compatible_text_provider import (
    LocalOpenAICompatibleTextProvider,
)
from app.services.provider_execution_config import resolve_provider_execution_config
from tests.unit.test_provider_gateway import _request


def test_local_openai_compatible_text_provider_returns_usage_without_api_key(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.live_text_model_id = "qwen3:8b"
    settings.live_text_provider_api_key = None
    settings.live_text_input_cost_per_1k_tokens = 0.0
    settings.live_text_output_cost_per_1k_tokens = 0.0

    monkeypatch.setattr(
        "app.providers.openai_compatible_text_transport.post_openai_compatible_response",
        lambda **_: {
            "id": "resp_local_123",
            "model": "qwen3:8b",
            "output_text": "Local provider explanation.",
            "usage": {"input_tokens": 120, "output_tokens": 40, "total_tokens": 160},
        },
    )

    response = LocalOpenAICompatibleTextProvider().execute(
        _request(), config=resolve_provider_execution_config()
    )

    assert response.provider_id == "text.local"
    assert response.provider_mode == "local_openai_compatible"
    assert response.stubbed is False
    assert response.model_id == "qwen3:8b"
    assert response.provider_request_id == "resp_local_123"
    assert response.input_tokens == 120
    assert response.output_tokens == 40
    assert response.total_tokens == 160
    assert response.message == "Local provider explanation."


def test_local_openai_compatible_text_provider_maps_missing_output_to_upstream_error(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.live_text_model_id = "qwen3:8b"
    settings.live_text_provider_api_key = None

    monkeypatch.setattr(
        "app.providers.openai_compatible_text_transport.post_openai_compatible_response",
        lambda **_: {
            "id": "resp_local_bad_123",
            "model": "qwen3:8b",
            "usage": {"input_tokens": 120, "output_tokens": 40, "total_tokens": 160},
        },
    )

    try:
        LocalOpenAICompatibleTextProvider().execute(
            _request(), config=resolve_provider_execution_config()
        )
    except ProviderExecutionError as exc:
        assert exc.category == ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR
        assert "did not include output text" in exc.message
    else:
        raise AssertionError("Expected ProviderExecutionError for malformed local response")


def test_local_openai_compatible_text_provider_maps_timeout_failures(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.live_text_model_id = "qwen3:8b"
    settings.live_text_provider_api_key = None

    def _raise_timeout(**_: object) -> dict[str, object]:
        raise ProviderExecutionError(
            category=ProviderFailureCategory.PROVIDER_TIMEOUT,
            message="Local provider request exceeded the configured timeout.",
        )

    monkeypatch.setattr(
        "app.providers.openai_compatible_text_transport.post_openai_compatible_response",
        _raise_timeout,
    )

    try:
        LocalOpenAICompatibleTextProvider().execute(
            _request(), config=resolve_provider_execution_config()
        )
    except ProviderExecutionError as exc:
        assert exc.category == ProviderFailureCategory.PROVIDER_TIMEOUT
        assert "configured timeout" in exc.message
    else:
        raise AssertionError("Expected ProviderExecutionError for local provider timeout")


def test_local_openai_compatible_text_provider_falls_back_when_model_echoes_contract_text(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.live_text_model_id = "qwen2.5:1.5b"
    settings.live_text_provider_api_key = None

    monkeypatch.setattr(
        "app.providers.openai_compatible_text_transport.post_openai_compatible_response",
        lambda **_: {
            "id": "resp_local_bad_summary",
            "model": "qwen2.5:1.5b",
            "output_text": (
                '{"grounded_summary":"The output contract for the structured Lotus domain with '
                'the provided data and context is as follows.",'
                '"talking_points":[],"recommended_actions":[],"risks_and_exceptions":[]}'
            ),
            "usage": {"input_tokens": 120, "output_tokens": 40, "total_tokens": 160},
        },
    )

    response = LocalOpenAICompatibleTextProvider().execute(
        config=resolve_provider_execution_config(),
        request=_request(
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
        ),
    )

    assert response.provider_mode == "local_openai_compatible"
    assert response.message.startswith("PB SG GLOBAL BAL 001 delivered 1.25% over YTD")
    assert response.structured_output["advisor_brief_guardrail_triggered"] is True
    assert response.structured_output["talking_points"]
