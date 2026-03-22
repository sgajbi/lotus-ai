from app.config import settings
from app.contracts.providers import ProviderFailureCategory, ProviderOperationsState
from app.services.provider_degradation_state import record_provider_failure
from app.services.provider_operations_status import build_provider_operations_status


def test_provider_operations_status_reports_rollout_blocked_foundation_posture() -> None:
    status = build_provider_operations_status()

    assert status.service == "lotus-ai"
    assert status.provider_mode == "disabled"
    assert status.operations_state == ProviderOperationsState.ROLLOUT_BLOCKED
    assert status.runtime_execution_enabled is False
    assert status.rollout_blocked is True
    assert status.quota_policy.quota_enforced is False
    assert status.budget_policy.budget_enforced is False
    assert status.degradation_status.status == "DOCUMENTED_ONLY"
    assert status.blocking_reasons


def test_provider_operations_status_reports_soft_budget_state_when_live_path_is_enabled() -> None:
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"
    settings.live_text_budget_enforced = True
    settings.live_text_input_cost_per_1k_tokens = 0.01
    settings.live_text_output_cost_per_1k_tokens = 0.03
    settings.live_text_soft_budget_usd = 0.5
    settings.live_text_hard_budget_usd = 1.0

    from app.contracts.providers import ProviderAdapterKind, ProviderExecutionResponse
    from app.services.provider_budget_policy import record_provider_spend

    record_provider_spend(
        ProviderExecutionResponse(
            provider_id="text.openai",
            provider_mode="openai",
            adapter_kind=ProviderAdapterKind.OPENAI_LIVE,
            failure_category=None,
            timeout_ms=4000,
            retry_count=0,
            max_output_tokens=512,
            model_id="gpt-5.4",
            provider_request_id="req-ops-1",
            input_tokens=100,
            output_tokens=200,
            total_tokens=300,
            estimated_cost_usd=0.75,
            stubbed=False,
            message="live response",
            structured_output={},
        )
    )

    status = build_provider_operations_status()

    assert status.operations_state == ProviderOperationsState.BUDGET_SOFT_LIMIT
    assert status.runtime_execution_enabled is True
    assert status.rollout_blocked is False
    assert any("soft budget threshold" in reason for reason in status.blocking_reasons)


def test_provider_operations_status_reports_circuit_open_state() -> None:
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

    record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)
    record_provider_failure(ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR)

    status = build_provider_operations_status()

    assert status.operations_state == ProviderOperationsState.CIRCUIT_OPEN
    assert status.degradation_status.status == "CIRCUIT_OPEN"
    assert status.degradation_status.timeout_failure_count == 1
    assert status.degradation_status.upstream_error_failure_count == 1
