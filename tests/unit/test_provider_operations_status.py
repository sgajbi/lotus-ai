from datetime import UTC, datetime
from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from app.config import settings
from app.contracts.providers import (
    ProviderExecutionRequest,
    ProviderFailureCategory,
    ProviderOperationsState,
)
from app.services.provider_degradation_state import record_provider_failure
from app.services.provider_operations_store import reset_provider_operations_store_cache
from app.services.rate_card_store import reset_rate_card_store_cache
from app.services.provider_operations_status import build_provider_operations_status
from tests.support.migration_runner import upgrade_database_to_head


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
    assert status.expansion_policy.bounded_expansion_enabled is True
    assert status.expansion_policy.expansion_blocked is False
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

    from app.services.provider_budget_policy import record_attempt_spend
    from app.services.provider_usage_accounting import AttemptDebit

    record_attempt_spend(
        execution_id="exec-ops-status-soft",
        candidate_entry_id="text.openai:gpt-5.4",
        provider_id="text.openai",
        model_revision="gpt-5.4",
        attempt_index=0,
        debit=AttemptDebit(
            amount_usd=0.75,
            basis="ACTUAL_USAGE",
            input_tokens=100,
            output_tokens=200,
            rate_card_ref="default-live-text",
        ),
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


def test_provider_operations_status_reports_invalid_quota_configuration() -> None:
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"
    settings.live_text_quota_enforced = True
    settings.live_text_task_quota_limits = "unknown-task=1"

    status = build_provider_operations_status()

    assert status.runtime_execution_enabled is True
    assert status.operations_state == ProviderOperationsState.OPERATIONS_INVALID
    assert any(
        "unknown or retrieval-backed task ids" in reason for reason in status.blocking_reasons
    )


def test_provider_operations_status_reports_invalid_budget_configuration() -> None:
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"
    settings.live_text_budget_enforced = True
    settings.live_text_hard_budget_usd = 1.0

    status = build_provider_operations_status()

    assert status.runtime_execution_enabled is True
    assert status.operations_state == ProviderOperationsState.OPERATIONS_INVALID
    assert any("effective live-text rate card" in reason for reason in status.blocking_reasons)


def test_provider_operations_summary_mentions_local_secret_go_live_block() -> None:
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"
    settings.secret_source_mode = "local_or_unspecified"

    status = build_provider_operations_status()

    assert any("production go-live remains blocked" in line for line in status.summary)


def test_provider_operations_status_does_not_globally_block_for_task_scoped_quota_exhaustion() -> (
    None
):
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"
    settings.live_text_quota_enforced = True
    settings.live_text_task_quota_limits = "explain.v1=1"

    from app.services.provider_quota_policy import enforce_provider_quota

    enforce_provider_quota(
        ProviderExecutionRequest(
            task_id="explain.v1",
            caller_app="lotus-manage",
            requested_by="ops.user@lotus",
            tenant_id="tenant-sg-001",
            prompt_version="foundation.explain.v1",
            system_instructions="Explain structured outputs conservatively.",
            output_contract_notes="Return explanation only.",
            output_label="EXPLANATION_ONLY",
            safety_mode="documented_only",
            redaction_posture="MINIMIZATION_REQUIRED",
            context_summary="Explain provider quota posture",
            context_payload={},
            source_refs=[],
            timeout_ms=4000,
            retry_limit=0,
            max_output_tokens=512,
        )
    )
    status = build_provider_operations_status()

    assert status.runtime_execution_enabled is True
    assert status.operations_state == ProviderOperationsState.NORMAL


def test_provider_operations_status_reports_rollout_blocked_with_invalid_quota_and_budget_details() -> (
    None
):
    settings.live_text_quota_enforced = True
    settings.live_text_task_quota_limits = "broken-entry"
    settings.live_text_budget_enforced = True

    status = build_provider_operations_status()

    assert status.operations_state == ProviderOperationsState.ROLLOUT_BLOCKED
    assert any("malformed" in reason for reason in status.blocking_reasons)
    assert any("configured hard budget threshold" in reason for reason in status.blocking_reasons)


def test_provider_operations_status_reports_default_quota_exhaustion_as_global_block() -> None:
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"
    settings.live_text_quota_enforced = True
    settings.live_text_default_quota_limit = 1

    from app.services.provider_quota_policy import enforce_provider_quota

    enforce_provider_quota(
        ProviderExecutionRequest(
            task_id="explain.v1",
            caller_app="lotus-manage",
            requested_by="ops.user@lotus",
            tenant_id="tenant-sg-001",
            prompt_version="foundation.explain.v1",
            system_instructions="Explain structured outputs conservatively.",
            output_contract_notes="Return explanation only.",
            output_label="EXPLANATION_ONLY",
            safety_mode="documented_only",
            redaction_posture="MINIMIZATION_REQUIRED",
            context_summary="Explain provider quota posture",
            context_payload={},
            source_refs=[],
            timeout_ms=4000,
            retry_limit=0,
            max_output_tokens=512,
        )
    )

    status = build_provider_operations_status()

    assert status.operations_state == ProviderOperationsState.QUOTA_BLOCKED
    assert any(
        "default live-provider quota scope is currently exhausted" in reason
        for reason in status.blocking_reasons
    )


def test_provider_operations_status_reports_hard_budget_blocked_state() -> None:
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

    from app.services.provider_budget_policy import record_attempt_spend
    from app.services.provider_usage_accounting import AttemptDebit

    record_attempt_spend(
        execution_id="exec-ops-status-hard",
        candidate_entry_id="text.openai:gpt-5.4",
        provider_id="text.openai",
        model_revision="gpt-5.4",
        attempt_index=0,
        debit=AttemptDebit(
            amount_usd=1.0,
            basis="ACTUAL_USAGE",
            input_tokens=100,
            output_tokens=200,
            rate_card_ref="default-live-text",
        ),
    )

    status = build_provider_operations_status()

    assert status.operations_state == ProviderOperationsState.BUDGET_BLOCKED
    assert any(
        "hard budget posture is currently blocking" in reason for reason in status.blocking_reasons
    )


def test_provider_operations_status_reports_degraded_upstream_state() -> None:
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

    status = build_provider_operations_status()

    assert status.operations_state == ProviderOperationsState.DEGRADED_UPSTREAM
    assert any("currently degraded" in reason for reason in status.blocking_reasons)


def test_provider_operations_status_reports_persisted_circuit_state_after_store_reset(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-provider-ops.db'}"
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
    upgrade_database_to_head(settings.database_url)

    fixed_now = datetime(2026, 3, 23, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(
        "app.services.provider_degradation_state._utcnow",
        lambda: fixed_now,
    )

    record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)
    record_provider_failure(ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR)
    reset_provider_operations_store_cache()
    reset_rate_card_store_cache()

    status = build_provider_operations_status()

    assert status.operations_state == ProviderOperationsState.CIRCUIT_OPEN
    assert status.degradation_status.status == "CIRCUIT_OPEN"
    assert status.degradation_status.timeout_failure_count == 1
    assert status.degradation_status.upstream_error_failure_count == 1
