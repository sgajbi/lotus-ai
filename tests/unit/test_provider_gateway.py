import pytest
from fastapi import HTTPException

from app.config import settings
from app.contracts.providers import ProviderAdapterKind, ProviderExecutionRequest
from app.services.provider_gateway import execute_text_generation


def test_execute_text_generation_routes_through_stub_provider() -> None:
    response = execute_text_generation(
        ProviderExecutionRequest(
            task_id="explain.v1",
            caller_app="lotus-manage",
            prompt_version="foundation.explain.v1",
            output_label="EXPLANATION_ONLY",
            safety_mode="documented_only",
            redaction_posture="MINIMIZATION_REQUIRED",
            context_summary="Explain rebalance outcome",
            context_payload={"status": "BLOCKED", "rule_count": 3},
            source_refs=["lotus-manage:run:reb_001"],
        )
    )

    assert response.provider_id == "text.stub"
    assert response.provider_mode == "disabled"
    assert response.adapter_kind == ProviderAdapterKind.STUB
    assert response.stubbed is True
    assert response.structured_output["provider_id"] == "text.stub"
    assert response.structured_output["adapter_kind"] == "STUB"
    assert response.structured_output["context_keys"] == ["rule_count", "status"]
    assert response.structured_output["output_label"] == "EXPLANATION_ONLY"
    assert response.structured_output["redaction_posture"] == "MINIMIZATION_REQUIRED"


def test_execute_text_generation_rejects_unsupported_provider_mode() -> None:
    settings.provider_mode = "openai"

    with pytest.raises(HTTPException) as exc_info:
        execute_text_generation(
            ProviderExecutionRequest(
                task_id="explain.v1",
                caller_app="lotus-manage",
                prompt_version="foundation.explain.v1",
                output_label="EXPLANATION_ONLY",
                safety_mode="documented_only",
                redaction_posture="MINIMIZATION_REQUIRED",
                context_summary="Explain rebalance outcome",
                context_payload={"status": "BLOCKED"},
                source_refs=[],
            )
        )

    assert exc_info.value.status_code == 503
    assert "not supported in the current phase" in str(exc_info.value.detail)

    settings.provider_mode = "disabled"


def test_execute_text_generation_routes_stub_mode_through_stub_provider() -> None:
    settings.provider_mode = "stub"

    response = execute_text_generation(
        ProviderExecutionRequest(
            task_id="summarize.v1",
            caller_app="lotus-advise",
            prompt_version="foundation.summarize.v1",
            output_label="DRAFT",
            safety_mode="documented_only",
            redaction_posture="MINIMIZATION_REQUIRED",
            context_summary="Summarize proposal workflow",
            context_payload={"status": "PENDING_REVIEW"},
            source_refs=[],
        )
    )

    assert response.provider_id == "text.stub"
    assert response.provider_mode == "stub"
    assert response.adapter_kind == ProviderAdapterKind.STUB
    assert response.stubbed is True
    assert response.structured_output["output_label"] == "DRAFT"

    settings.provider_mode = "disabled"
