from pathlib import Path

from fastapi import HTTPException

from app.config import settings
from app.contracts.providers import (
    ProviderAdapterKind,
    ProviderExecutionResponse,
    ProviderFailureCategory,
    ProviderQuotaScope,
)
from app.contracts.provider_operations import (
    ProviderOperationsResetApprovalResponse,
    ProviderOperationsControlActionType,
    ProviderOperationsResetApprovalRequest,
    ProviderOperationsResetIntentRequest,
)
from app.http.authenticated_caller import AuthenticatedCaller
from app.services.provider_budget_policy import record_provider_spend
from app.services.provider_degradation_state import record_provider_failure
from app.services.provider_operations_control import (
    approve_provider_operations_reset,
    build_provider_operations_control_history,
    request_provider_operations_reset,
)
from tests.support.governed_control import GOVERNED_APPROVER, GOVERNED_REQUESTER
from app.services.provider_quota_policy import enforce_provider_quota
from app.services.provider_request_builder import build_provider_execution_request
from app.services.task_execution_pipeline import validate_task_request
from tests.support.migration_runner import upgrade_database_to_head
from tests.unit.test_task_executor import _request


def _budget_response(cost: float) -> ProviderExecutionResponse:
    return ProviderExecutionResponse(
        provider_id="text.openai",
        provider_mode="openai",
        adapter_kind=ProviderAdapterKind.OPENAI_LIVE,
        failure_category=None,
        timeout_ms=4000,
        retry_count=0,
        max_output_tokens=512,
        model_id="gpt-5.4",
        provider_request_id="req-provider-ops-control-1",
        input_tokens=100,
        output_tokens=200,
        total_tokens=300,
        estimated_cost_usd=cost,
        stubbed=False,
        message="live response",
        structured_output={},
    )


def _governed_reset(
    action_type: ProviderOperationsControlActionType,
    *,
    scope: ProviderQuotaScope | None = None,
    scope_key: str | None = None,
    reason: str = "Clear durable provider controls after reviewed recovery.",
) -> ProviderOperationsResetApprovalResponse:
    pending = request_provider_operations_reset(
        ProviderOperationsResetIntentRequest(
            action_type=action_type,
            scope=scope,
            scope_key=scope_key,
            reason=reason,
            requested_by="ops.user@lotus",
        ),
        GOVERNED_REQUESTER,
    )
    return approve_provider_operations_reset(
        ProviderOperationsResetApprovalRequest(
            action_type=action_type,
            scope=scope,
            scope_key=scope_key,
            action_id=pending.governed_action.action_id,
            action_hash=pending.governed_action.action_hash,
            approved_by="approver.user@lotus",
        ),
        GOVERNED_APPROVER,
    )


def test_provider_operations_control_history_reports_unsupported_in_memory_posture() -> None:
    history = build_provider_operations_control_history()

    assert history.reset_actions_supported is False
    assert history.control_plane_store_mode == "memory"
    assert history.latest_events == []


def test_provider_operations_control_action_resets_durable_state_and_records_event(
    tmp_path: Path,
) -> None:
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-provider-ops-control.db'}"
    settings.live_text_quota_enforced = True
    settings.live_text_default_quota_limit = 2
    settings.live_text_budget_enforced = True
    settings.live_text_input_cost_per_1k_tokens = 0.01
    settings.live_text_output_cost_per_1k_tokens = 0.03
    settings.live_text_hard_budget_usd = 1.0
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 1
    settings.live_text_circuit_open_failure_count_threshold = 2
    settings.live_text_circuit_open_seconds = 60
    upgrade_database_to_head(settings.database_url)

    provider_request = build_provider_execution_request(
        context=validate_task_request(_request("explain.v1"))
    )
    enforce_provider_quota(provider_request)
    record_provider_spend(_budget_response(0.75))
    record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)

    response = _governed_reset(ProviderOperationsControlActionType.RESET_ALL_PROVIDER_OPERATIONS)
    history = build_provider_operations_control_history()

    assert response.event.affected_record_count == 3
    assert response.governed_action.status.value == "EXECUTED"
    assert response.governed_action.requester_key_id == "ops-key-alpha"
    assert response.governed_action.approver_key_id == "ops-key-beta"
    # The durable event records verified credential identities, not the
    # caller-typed names.
    assert "ops-key-alpha" in response.event.requested_by
    assert "ops-key-beta" in response.event.approved_by
    assert history.reset_actions_supported is True
    assert history.latest_events[0].event_id == response.event.event_id
    assert (
        history.latest_events[0].action_type
        == ProviderOperationsControlActionType.RESET_ALL_PROVIDER_OPERATIONS
    )


def test_provider_operations_control_action_rejects_missing_targeted_quota_scope() -> None:
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.database_url = "sqlite:///:memory:"

    try:
        request_provider_operations_reset(
            ProviderOperationsResetIntentRequest(
                action_type=ProviderOperationsControlActionType.RESET_QUOTA_SCOPE,
                reason="Targeted quota reset.",
            ),
            GOVERNED_REQUESTER,
        )
    except HTTPException as exc:
        assert exc.status_code == 422
    else:
        raise AssertionError("Expected targeted quota reset without scope to be rejected.")


def test_provider_operations_control_action_rejects_nondurable_store_mode() -> None:
    try:
        request_provider_operations_reset(
            ProviderOperationsResetIntentRequest(
                action_type=ProviderOperationsControlActionType.RESET_BUDGET,
                reason="Budget reset on in-memory store should fail.",
            ),
            GOVERNED_REQUESTER,
        )
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError(
            "Expected in-memory provider operations control action to be rejected."
        )


def test_provider_operations_control_action_resets_targeted_quota_scope(tmp_path: Path) -> None:
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-provider-ops-control.db'}"
    settings.live_text_quota_enforced = True
    settings.live_text_task_quota_limits = "explain.v1=2"
    upgrade_database_to_head(settings.database_url)

    provider_request = build_provider_execution_request(
        context=validate_task_request(_request("explain.v1"))
    )
    enforce_provider_quota(provider_request)

    response = _governed_reset(
        ProviderOperationsControlActionType.RESET_QUOTA_SCOPE,
        scope=ProviderQuotaScope.TASK,
        scope_key="explain.v1",
        reason="Targeted task quota reset after review.",
    )

    assert response.event.affected_record_count == 1
    assert response.event.scope == ProviderQuotaScope.TASK
    assert response.event.scope_key == "explain.v1"


def test_provider_operations_control_action_blocks_unauthorized_caller(tmp_path: Path) -> None:
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-provider-ops-unauthorized.db'}"
    upgrade_database_to_head(settings.database_url)

    unauthorized = AuthenticatedCaller(
        caller_app="lotus-workbench",
        trust_source="verified_service_jwt",
        credential_key_id="ops-key-alpha",
    )
    try:
        request_provider_operations_reset(
            ProviderOperationsResetIntentRequest(
                action_type=ProviderOperationsControlActionType.RESET_BUDGET,
                reason="Unauthorized budget reset attempt.",
            ),
            unauthorized,
        )
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "not authorized for provider control-plane actions" in str(exc.detail)
    else:
        raise AssertionError("Expected unauthorized provider control action to be rejected.")


def test_a_reset_cannot_be_self_approved_and_state_survives(tmp_path: Path) -> None:
    """The target invariant on the provider domain: the requester's own
    credential cannot execute the reset, and the state the reset would clear
    is still there afterwards."""

    settings.provider_operations_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-provider-ops-self.db'}"
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 1
    settings.live_text_circuit_open_failure_count_threshold = 2
    settings.live_text_circuit_open_seconds = 60
    upgrade_database_to_head(settings.database_url)

    record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)
    pending = request_provider_operations_reset(
        ProviderOperationsResetIntentRequest(
            action_type=ProviderOperationsControlActionType.RESET_DEGRADATION,
            reason="Self-approval attempt.",
        ),
        GOVERNED_REQUESTER,
    )

    try:
        approve_provider_operations_reset(
            ProviderOperationsResetApprovalRequest(
                action_type=ProviderOperationsControlActionType.RESET_DEGRADATION,
                action_id=pending.governed_action.action_id,
                action_hash=pending.governed_action.action_hash,
            ),
            GOVERNED_REQUESTER,
        )
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "distinct" in str(exc.detail)
    else:
        raise AssertionError("Expected self-approval to be refused.")
    from app.services.provider_degradation_state import build_provider_degradation_status

    assert build_provider_degradation_status().consecutive_failure_count == 1


def test_an_approval_cannot_be_redirected_to_a_different_reset_shape(
    tmp_path: Path,
) -> None:
    """The approver restates the reset shape; approving a degradation clear
    with a pending budget-reset action refuses rather than executing either."""

    settings.provider_operations_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-provider-ops-redirect.db'}"
    upgrade_database_to_head(settings.database_url)

    pending = request_provider_operations_reset(
        ProviderOperationsResetIntentRequest(
            action_type=ProviderOperationsControlActionType.RESET_BUDGET,
            reason="Budget reset pending.",
        ),
        GOVERNED_REQUESTER,
    )

    try:
        approve_provider_operations_reset(
            ProviderOperationsResetApprovalRequest(
                action_type=ProviderOperationsControlActionType.RESET_DEGRADATION,
                action_id=pending.governed_action.action_id,
                action_hash=pending.governed_action.action_hash,
            ),
            GOVERNED_APPROVER,
        )
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "cannot be redirected" in str(exc.detail)
    else:
        raise AssertionError("Expected shape-redirected approval to be refused.")
