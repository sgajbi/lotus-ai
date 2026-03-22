from app.config import settings
from app.contracts.providers import ProviderCredentialStatus, ProviderRolloutState
from app.services.provider_activation_readiness import build_provider_activation_readiness


def test_provider_activation_readiness_reports_foundation_blockers() -> None:
    readiness = build_provider_activation_readiness()

    assert readiness.service == "lotus-ai"
    assert readiness.activation_ready is False
    assert readiness.provider_mode == "disabled"
    assert readiness.embedding_provider_mode == "disabled"
    assert (
        readiness.text_generation_configuration.rollout_state == ProviderRolloutState.STUB_DEFAULT
    )
    assert (
        readiness.text_generation_configuration.credential_status
        == ProviderCredentialStatus.NOT_CONFIGURED
    )
    assert len(readiness.blocking_findings) == 4
    assert len(readiness.activation_path) == 8


def test_provider_activation_readiness_reports_ready_when_live_execution_is_enabled() -> None:
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"

    readiness = build_provider_activation_readiness()

    assert readiness.activation_ready is True
    assert "/platform/providers/governance-status" in readiness.activation_path[-1]


def test_provider_activation_readiness_reports_invalid_live_configuration() -> None:
    settings.provider_rollout_state = "ALLOWLISTED_DISABLED"
    settings.live_text_provider_id = "text.openai"

    readiness = build_provider_activation_readiness()

    assert readiness.text_generation_configuration.configuration_valid is False
    assert any("partially populated" in finding for finding in readiness.blocking_findings)


def test_provider_activation_readiness_reports_invalid_quota_configuration() -> None:
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"
    settings.live_text_quota_enforced = True
    settings.live_text_task_quota_limits = "broken-entry"

    readiness = build_provider_activation_readiness()

    assert readiness.activation_ready is False
    assert any("malformed" in finding for finding in readiness.blocking_findings)


def test_provider_activation_readiness_reports_invalid_budget_configuration() -> None:
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"
    settings.live_text_budget_enforced = True

    readiness = build_provider_activation_readiness()

    assert readiness.activation_ready is False
    assert any("budget enforcement requires" in finding for finding in readiness.blocking_findings)


def test_provider_activation_readiness_reports_hard_budget_blocking() -> None:
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
            provider_request_id="req-budget-hard-1",
            input_tokens=100,
            output_tokens=200,
            total_tokens=300,
            estimated_cost_usd=1.0,
            stubbed=False,
            message="live response",
            structured_output={},
        )
    )

    readiness = build_provider_activation_readiness()

    assert readiness.activation_ready is False
    assert any(
        "hard budget posture is currently blocking" in finding
        for finding in readiness.blocking_findings
    )


def test_provider_activation_readiness_reports_degraded_upstream_blocking() -> None:
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

    from app.contracts.providers import ProviderFailureCategory
    from app.services.provider_degradation_state import record_provider_failure

    record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)

    readiness = build_provider_activation_readiness()

    assert readiness.activation_ready is False
    assert any("currently degraded" in finding for finding in readiness.blocking_findings)
