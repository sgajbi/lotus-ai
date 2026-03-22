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
        "requested_by": "ops.user@lotus",
        "tenant_id": "tenant-sg-001",
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


def test_execute_text_generation_rejects_live_provider_when_quota_is_exceeded() -> None:
    class _LiveAdapter:
        def execute(self, request: ProviderExecutionRequest) -> object:
            return type(
                "Response",
                (),
                {
                    "provider_id": "text.openai",
                    "provider_mode": "openai",
                    "adapter_kind": ProviderAdapterKind.OPENAI_LIVE,
                    "failure_category": None,
                    "timeout_ms": request.timeout_ms,
                    "retry_count": 0,
                    "max_output_tokens": request.max_output_tokens,
                    "model_id": "gpt-5.4",
                    "provider_request_id": "req_quota_1",
                    "input_tokens": 10,
                    "output_tokens": 20,
                    "total_tokens": 30,
                    "estimated_cost_usd": 0.01,
                    "stubbed": False,
                    "message": "live response",
                    "structured_output": {},
                },
            )()

    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"
    settings.live_text_quota_enforced = True
    settings.live_text_task_quota_limits = "explain.v1=1"
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "app.services.provider_gateway.resolve_text_generation_adapter",
        lambda mode: _LiveAdapter(),
    )

    first_response = execute_text_generation(_request())
    assert first_response.provider_id == "text.openai"

    with pytest.raises(HTTPException) as exc_info:
        execute_text_generation(_request())

    assert exc_info.value.status_code == 503
    assert "QUOTA_EXCEEDED" in str(exc_info.value.detail)
    monkeypatch.undo()


def test_execute_text_generation_rejects_live_provider_when_budget_is_exceeded() -> None:
    class _LiveAdapter:
        def execute(self, request: ProviderExecutionRequest) -> object:
            return type(
                "Response",
                (),
                {
                    "provider_id": "text.openai",
                    "provider_mode": "openai",
                    "adapter_kind": ProviderAdapterKind.OPENAI_LIVE,
                    "failure_category": None,
                    "timeout_ms": request.timeout_ms,
                    "retry_count": 0,
                    "max_output_tokens": request.max_output_tokens,
                    "model_id": "gpt-5.4",
                    "provider_request_id": "req_budget_1",
                    "input_tokens": 10,
                    "output_tokens": 20,
                    "total_tokens": 30,
                    "estimated_cost_usd": 1.0,
                    "stubbed": False,
                    "message": "live response",
                    "structured_output": {},
                },
            )()

    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"
    settings.live_text_budget_enforced = True
    settings.live_text_input_cost_per_1k_tokens = 0.01
    settings.live_text_output_cost_per_1k_tokens = 0.03
    settings.live_text_hard_budget_usd = 1.0
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "app.services.provider_gateway.resolve_text_generation_adapter",
        lambda mode: _LiveAdapter(),
    )

    first_response = execute_text_generation(_request())
    assert first_response.provider_id == "text.openai"

    with pytest.raises(HTTPException) as exc_info:
        execute_text_generation(_request())

    assert exc_info.value.status_code == 503
    assert "BUDGET_EXCEEDED" in str(exc_info.value.detail)
    monkeypatch.undo()


def test_execute_text_generation_opens_circuit_after_repeated_provider_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _BrokenLiveAdapter:
        def execute(self, request: ProviderExecutionRequest) -> object:
            raise ProviderExecutionError(
                category=ProviderFailureCategory.PROVIDER_TIMEOUT,
                message="simulated timeout",
            )

    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 1
    settings.live_text_circuit_open_failure_count_threshold = 2
    settings.live_text_circuit_open_seconds = 60
    monkeypatch.setattr(
        "app.services.provider_gateway.resolve_text_generation_adapter",
        lambda mode: _BrokenLiveAdapter(),
    )

    with pytest.raises(HTTPException) as first_exc:
        execute_text_generation(_request())
    assert "PROVIDER_TIMEOUT" in str(first_exc.value.detail)

    with pytest.raises(HTTPException) as second_exc:
        execute_text_generation(_request())
    assert "PROVIDER_TIMEOUT" in str(second_exc.value.detail)

    with pytest.raises(HTTPException) as third_exc:
        execute_text_generation(_request())
    assert "CIRCUIT_OPEN" in str(third_exc.value.detail)


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
