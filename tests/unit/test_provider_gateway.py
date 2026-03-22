import pytest
from fastapi import HTTPException

from app.config import settings
from app.contracts.providers import (
    ProviderAdapterKind,
    ProviderExecutionRequest,
    ProviderFailureCategory,
)
from app.providers.base import ProviderExecutionError
from app.services.provider_gateway import execute_text_generation


def _request(**overrides: object) -> ProviderExecutionRequest:
    payload: dict[str, object] = {
        "task_id": "explain.v1",
        "caller_app": "lotus-manage",
        "prompt_version": "foundation.explain.v1",
        "system_instructions": "Explain structured outputs conservatively.",
        "output_contract_notes": "Return explanation only. Avoid unsupported recommendations.",
        "output_label": "EXPLANATION_ONLY",
        "safety_mode": "documented_only",
        "redaction_posture": "MINIMIZATION_REQUIRED",
        "context_summary": "Explain rebalance outcome",
        "context_payload": {"status": "BLOCKED", "rule_count": 3},
        "source_refs": ["lotus-manage:run:reb_001"],
        "timeout_ms": 4000,
        "retry_limit": 0,
        "max_output_tokens": 512,
    }
    payload.update(overrides)
    return ProviderExecutionRequest.model_validate(payload)


def test_execute_text_generation_routes_through_stub_provider() -> None:
    response = execute_text_generation(_request())

    assert response.provider_id == "text.stub"
    assert response.provider_mode == "disabled"
    assert response.adapter_kind == ProviderAdapterKind.STUB
    assert response.failure_category is None
    assert response.timeout_ms == 4000
    assert response.retry_count == 0
    assert response.max_output_tokens == 512
    assert response.stubbed is True
    assert response.structured_output["provider_id"] == "text.stub"
    assert response.structured_output["adapter_kind"] == "STUB"
    assert response.structured_output["timeout_ms"] == 4000
    assert response.structured_output["retry_count"] == 0
    assert response.structured_output["max_output_tokens"] == 512
    assert response.structured_output["context_keys"] == ["rule_count", "status"]
    assert response.structured_output["output_label"] == "EXPLANATION_ONLY"
    assert response.structured_output["redaction_posture"] == "MINIMIZATION_REQUIRED"


def test_execute_text_generation_rejects_blocked_live_provider_mode() -> None:
    settings.provider_mode = "openai"

    with pytest.raises(HTTPException) as exc_info:
        execute_text_generation(_request(context_payload={"status": "BLOCKED"}, source_refs=[]))

    assert exc_info.value.status_code == 503
    assert "LIVE_EXECUTION_NOT_ENABLED" in str(exc_info.value.detail)

    settings.provider_mode = "disabled"


def test_execute_text_generation_routes_stub_mode_through_stub_provider() -> None:
    settings.provider_mode = "stub"

    response = execute_text_generation(
        _request(
            task_id="summarize.v1",
            caller_app="lotus-advise",
            prompt_version="foundation.summarize.v1",
            system_instructions="Summarize structured inputs conservatively.",
            output_contract_notes="Return draft summary only.",
            output_label="DRAFT",
            context_summary="Summarize proposal workflow",
            context_payload={"status": "PENDING_REVIEW"},
            source_refs=[],
        )
    )

    assert response.provider_id == "text.stub"
    assert response.provider_mode == "stub"
    assert response.adapter_kind == ProviderAdapterKind.STUB
    assert response.timeout_ms == 4000
    assert response.retry_count == 0
    assert response.max_output_tokens == 512
    assert response.stubbed is True
    assert response.structured_output["output_label"] == "DRAFT"

    settings.provider_mode = "disabled"


def test_execute_text_generation_rejects_adapter_execution_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _BrokenAdapter:
        def execute(self, request: ProviderExecutionRequest) -> object:
            raise ProviderExecutionError(
                category=ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR,
                message="simulated upstream failure",
            )

    settings.provider_mode = "stub"
    monkeypatch.setattr(
        "app.services.provider_gateway.resolve_text_generation_adapter",
        lambda mode: _BrokenAdapter(),
    )

    with pytest.raises(HTTPException) as exc_info:
        execute_text_generation(_request())

    assert exc_info.value.status_code == 503
    assert "PROVIDER_UPSTREAM_ERROR" in str(exc_info.value.detail)

    settings.provider_mode = "disabled"
