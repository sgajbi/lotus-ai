"""Kill-switch control actions and gateway enforcement (issue #177, slice 1)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.config import settings
from app.contracts.kill_switches import (
    KillSwitchActivationRecord,
    KillSwitchActivationRequest,
    KillSwitchClearApprovalRequest,
    KillSwitchClearIntentRequest,
    KillSwitchScope,
)
from app.http.authenticated_caller import AuthenticatedCaller
from app.contracts.providers import (
    ProviderExecutionRequest,
    ProviderFailureCategory,
)
from app.providers.base import ProviderExecutionError
from app.services.kill_switch_control import (
    activate_kill_switch,
    approve_kill_switch_clearance,
    build_kill_switch_status,
    enforce_kill_switches,
    request_kill_switch_clearance,
)
from app.services.kill_switch_store import (
    get_kill_switch_repository,
    reset_kill_switch_store_cache,
)
from app.services.model_catalogue_store import reset_model_catalogue_store_cache
from app.services.provider_gateway import (
    ProviderGatewayUnavailableError,
    execute_text_generation,
)
from app.services.provider_quota_policy import reset_provider_quota_counters
from tests.support.migration_runner import upgrade_database_to_head

CONTROL_CALLER = "lotus-platform"


@pytest.fixture(autouse=True)
def _fresh_kill_switch_store() -> Iterator[None]:
    reset_kill_switch_store_cache()
    yield
    reset_kill_switch_store_cache()


@pytest.fixture
def _durable_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'kill-switches.db'}"
    upgrade_database_to_head(database_url)
    monkeypatch.setattr(settings, "kill_switch_store_mode", "sqlalchemy")
    monkeypatch.setattr(settings, "database_url", database_url)


def _activation_request(**overrides: object) -> KillSwitchActivationRequest:
    payload: dict[str, object] = {
        "caller_app": CONTROL_CALLER,
        "scope": KillSwitchScope.TASK,
        "target": "explain.v1",
        "reason": "Incident LOTUS-4711: unsafe outputs observed for this task.",
        "requested_by": "ops.primary@lotus",
        "approved_by": "ops.secondary@lotus",
    }
    payload.update(overrides)
    return KillSwitchActivationRequest.model_validate(payload)


def _provider_request(**overrides: object) -> ProviderExecutionRequest:
    payload: dict[str, object] = {
        "task_id": "explain.v1",
        "caller_app": "lotus-manage",
        "requested_by": "ops.user@lotus",
        "tenant_id": "tenant-sg-001",
        "prompt_version": "foundation.explain.v1",
        "system_instructions": "Explain conservatively.",
        "output_contract_notes": "Explanation only.",
        "output_label": "EXPLANATION_ONLY",
        "safety_mode": "documented_only",
        "redaction_posture": "MINIMIZATION_REQUIRED",
        "context_summary": "Explain rebalance outcome",
        "context_payload": {"status": "BLOCKED"},
        "source_refs": ["lotus-manage:run:reb_001"],
        "timeout_ms": 4000,
        "retry_limit": 0,
        "max_output_tokens": 512,
    }
    payload.update(overrides)
    return ProviderExecutionRequest.model_validate(payload)


def test_activation_requires_the_durable_store() -> None:
    with pytest.raises(HTTPException) as exc_info:
        activate_kill_switch(_activation_request())
    assert exc_info.value.status_code == 409
    assert "LOTUS_AI_KILL_SWITCH_STORE_MODE=sqlalchemy" in str(exc_info.value.detail)


def test_activation_requires_provider_control_authorization(_durable_store: None) -> None:
    with pytest.raises(HTTPException) as exc_info:
        activate_kill_switch(_activation_request(caller_app="lotus-manage"))
    assert exc_info.value.status_code == 403


def test_activation_validates_scope_target_pairing(_durable_store: None) -> None:
    with pytest.raises(HTTPException) as exc_info:
        activate_kill_switch(
            _activation_request(scope=KillSwitchScope.ALL_LIVE_TEXT, target="text.openai")
        )
    assert exc_info.value.status_code == 422

    with pytest.raises(HTTPException) as exc_info:
        activate_kill_switch(_activation_request(scope=KillSwitchScope.PROVIDER, target=None))
    assert exc_info.value.status_code == 422

    with pytest.raises(HTTPException) as exc_info:
        activate_kill_switch(_activation_request(expires_at_utc="not-a-timestamp"))
    assert exc_info.value.status_code == 422


REQUESTER = AuthenticatedCaller(
    caller_app=CONTROL_CALLER,
    trust_source="verified_service_jwt",
    credential_key_id="ops-key-alpha",
)
APPROVER = AuthenticatedCaller(
    caller_app=CONTROL_CALLER,
    trust_source="verified_service_jwt",
    credential_key_id="ops-key-beta",
)


def _intent(
    reason: str = "Incident resolved; provider outputs verified safe.",
) -> KillSwitchClearIntentRequest:
    return KillSwitchClearIntentRequest(reason=reason, requested_by="ops.primary@lotus")


def test_activate_then_governed_clear_lifecycle(_durable_store: None) -> None:
    """Issue #157: activation stops execution on one authorized principal,
    immediately; clearance resumes it only through a verified requester and a
    DISTINCT verified approver bound to the exact action hash."""

    activated = activate_kill_switch(_activation_request())
    assert activated.store_mode == "sqlalchemy"
    switch_id = activated.activation.switch_id
    assert build_kill_switch_status().active_count == 1

    pending = request_kill_switch_clearance(switch_id, _intent(), REQUESTER)
    action = pending.governed_action
    assert action.status.value == "PENDING"
    assert action.requester_key_id == "ops-key-alpha"
    # The switch keeps enforcing until the approval executes.
    assert build_kill_switch_status().active_count == 1

    cleared = approve_kill_switch_clearance(
        switch_id,
        KillSwitchClearApprovalRequest(
            action_id=action.action_id,
            action_hash=action.action_hash,
            approved_by="ops.secondary@lotus",
        ),
        APPROVER,
    )
    assert cleared.activation.cleared_at is not None
    assert "ops-key-beta" in str(cleared.activation.cleared_by)
    assert cleared.governed_action.status.value == "EXECUTED"
    assert cleared.governed_action.requester_key_id == "ops-key-alpha"
    assert cleared.governed_action.approver_key_id == "ops-key-beta"
    assert build_kill_switch_status().active_count == 0

    with pytest.raises(HTTPException) as exc_info:
        request_kill_switch_clearance(switch_id, _intent("Duplicate clear."), REQUESTER)
    assert exc_info.value.status_code == 409

    with pytest.raises(HTTPException) as exc_info:
        request_kill_switch_clearance("ksw_does_not_exist", _intent(), REQUESTER)
    assert exc_info.value.status_code == 404


def test_no_single_credential_can_resume_stopped_execution(_durable_store: None) -> None:
    """The target invariant, end to end: the requester approving its own
    clearance is refused, and the switch keeps refusing execution."""

    activated = activate_kill_switch(_activation_request())
    switch_id = activated.activation.switch_id
    pending = request_kill_switch_clearance(switch_id, _intent(), REQUESTER)

    with pytest.raises(HTTPException) as exc_info:
        approve_kill_switch_clearance(
            switch_id,
            KillSwitchClearApprovalRequest(
                action_id=pending.governed_action.action_id,
                action_hash=pending.governed_action.action_hash,
            ),
            REQUESTER,
        )
    assert exc_info.value.status_code == 403
    assert build_kill_switch_status().active_count == 1
    with pytest.raises(ProviderExecutionError) as enforcement:
        enforce_kill_switches(_provider_request())
    assert enforcement.value.category is ProviderFailureCategory.KILL_SWITCH_ACTIVE


def test_header_trust_cannot_request_or_approve_clearance(_durable_store: None) -> None:
    activated = activate_kill_switch(_activation_request())
    switch_id = activated.activation.switch_id
    header_caller = AuthenticatedCaller(
        caller_app=CONTROL_CALLER,
        trust_source="trusted_http_header",
        credential_key_id=None,
    )

    with pytest.raises(HTTPException) as exc_info:
        request_kill_switch_clearance(switch_id, _intent(), header_caller)
    assert exc_info.value.status_code == 403

    pending = request_kill_switch_clearance(switch_id, _intent(), REQUESTER)
    with pytest.raises(HTTPException) as exc_info:
        approve_kill_switch_clearance(
            switch_id,
            KillSwitchClearApprovalRequest(
                action_id=pending.governed_action.action_id,
                action_hash=pending.governed_action.action_hash,
            ),
            header_caller,
        )
    assert exc_info.value.status_code == 403
    assert build_kill_switch_status().active_count == 1


def test_an_approval_binds_to_the_hash_and_cannot_be_redirected(
    _durable_store: None,
) -> None:
    first = activate_kill_switch(_activation_request())
    second = activate_kill_switch(
        _activation_request(target="summarize.v1", reason="Second incident.")
    )
    pending = request_kill_switch_clearance(first.activation.switch_id, _intent(), REQUESTER)

    with pytest.raises(HTTPException) as exc_info:
        approve_kill_switch_clearance(
            first.activation.switch_id,
            KillSwitchClearApprovalRequest(
                action_id=pending.governed_action.action_id, action_hash="0" * 64
            ),
            APPROVER,
        )
    assert exc_info.value.status_code == 409

    with pytest.raises(HTTPException) as exc_info:
        approve_kill_switch_clearance(
            second.activation.switch_id,
            KillSwitchClearApprovalRequest(
                action_id=pending.governed_action.action_id,
                action_hash=pending.governed_action.action_hash,
            ),
            APPROVER,
        )
    assert exc_info.value.status_code == 409
    assert build_kill_switch_status().active_count == 2


def test_enforcement_matches_every_scope_and_only_its_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "live_text_provider_id", "text.openai")
    monkeypatch.setattr(settings, "live_text_model_id", "gpt-5.4")
    monkeypatch.setattr(settings, "live_text_model_version", None)
    repository = get_kill_switch_repository()

    matching_cases = [
        (KillSwitchScope.ALL_LIVE_TEXT, None),
        (KillSwitchScope.PROVIDER, "text.openai"),
        (KillSwitchScope.MODEL_REVISION, "gpt-5.4"),
        (KillSwitchScope.TASK, "explain.v1"),
        (KillSwitchScope.TENANT, "tenant-sg-001"),
        (KillSwitchScope.CALLER_APP, "lotus-manage"),
    ]
    for index, (scope, target) in enumerate(matching_cases):
        reset_kill_switch_store_cache()
        repository = get_kill_switch_repository()
        repository.upsert_activation(
            _record(scope=scope, target=target, switch_id=f"ksw_match_{index}")
        )
        with pytest.raises(ProviderExecutionError) as exc_info:
            enforce_kill_switches(_provider_request())
        assert exc_info.value.category is ProviderFailureCategory.KILL_SWITCH_ACTIVE
        assert f"ksw_match_{index}" in exc_info.value.message

    non_matching_cases = [
        (KillSwitchScope.PROVIDER, "text.local"),
        (KillSwitchScope.MODEL_REVISION, "some-other-model"),
        (KillSwitchScope.TASK, "summarize.v1"),
        (KillSwitchScope.TENANT, "tenant-uk-999"),
        (KillSwitchScope.CALLER_APP, "lotus-gateway"),
    ]
    for index, (scope, target) in enumerate(non_matching_cases):
        reset_kill_switch_store_cache()
        get_kill_switch_repository().upsert_activation(
            _record(scope=scope, target=target, switch_id=f"ksw_miss_{index}")
        )
        enforce_kill_switches(_provider_request())


def test_enforcement_ignores_cleared_and_expired_activations() -> None:
    repository = get_kill_switch_repository()
    repository.upsert_activation(
        _record(
            scope=KillSwitchScope.TASK,
            target="explain.v1",
            switch_id="ksw_cleared",
            cleared_at="2026-08-30T00:00:00Z",
            cleared_by="ops.secondary@lotus",
            clear_reason="Resolved.",
        )
    )
    repository.upsert_activation(
        _record(
            scope=KillSwitchScope.TASK,
            target="explain.v1",
            switch_id="ksw_expired",
            expires_at_utc="2026-08-29T00:00:00Z",
        )
    )
    enforce_kill_switches(_provider_request())

    repository.upsert_activation(
        _record(
            scope=KillSwitchScope.TASK,
            target="explain.v1",
            switch_id="ksw_future_expiry",
            expires_at_utc="2099-01-01T00:00:00Z",
        )
    )
    with pytest.raises(ProviderExecutionError):
        enforce_kill_switches(_provider_request())


def test_gateway_refuses_before_the_adapter_with_a_recorded_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_model_catalogue_store_cache()
    reset_provider_quota_counters()
    monkeypatch.setattr(settings, "provider_mode", "openai")
    monkeypatch.setattr(settings, "provider_rollout_state", "CANARY_ENABLED")
    monkeypatch.setattr(settings, "live_text_provider_id", "text.openai")
    monkeypatch.setattr(settings, "live_text_model_id", "gpt-5.4")
    monkeypatch.setattr(settings, "live_text_model_version", None)
    monkeypatch.setattr(settings, "live_text_provider_api_key", "secret")
    monkeypatch.setattr(settings, "live_text_allowed_task_ids", "explain.v1")
    monkeypatch.setattr(settings, "live_text_quota_enforced", False)
    monkeypatch.setattr(settings, "live_text_budget_enforced", False)
    monkeypatch.setattr(settings, "live_text_degradation_enforced", False)
    monkeypatch.setattr(settings, "workflow_run_model_risk_inventory_json", "[]")

    get_kill_switch_repository().upsert_activation(
        _record(scope=KillSwitchScope.PROVIDER, target="text.openai", switch_id="ksw_gateway")
    )

    adapter_calls: list[str] = []

    def _record_adapter_resolution(mode: object) -> object:
        adapter_calls.append("resolved")
        return None

    monkeypatch.setattr(
        "app.services.provider_gateway.resolve_text_generation_adapter",
        _record_adapter_resolution,
    )

    with pytest.raises(ProviderGatewayUnavailableError) as exc_info:
        execute_text_generation(_provider_request())

    assert exc_info.value.status_code == 503
    assert "KILL_SWITCH_ACTIVE" in str(exc_info.value.detail)
    assert adapter_calls == [], "a kill switch must refuse before the adapter is resolved"
    decision = exc_info.value.routing_decision
    assert decision.selected_provider_id is None
    assert decision.candidates[0].rejection_reason is ProviderFailureCategory.KILL_SWITCH_ACTIVE
    reset_model_catalogue_store_cache()


def _record(**overrides: object) -> KillSwitchActivationRecord:
    payload: dict[str, object] = {
        "switch_id": "ksw_test",
        "scope": KillSwitchScope.TASK,
        "target": "explain.v1",
        "reason": "Test activation.",
        "requested_by": "ops.primary@lotus",
        "approved_by": "ops.secondary@lotus",
        "activated_at": "2026-08-30T00:00:00Z",
    }
    payload.update(overrides)
    return KillSwitchActivationRecord.model_validate(payload)


def test_memory_repository_get_and_ordering() -> None:
    repository = get_kill_switch_repository()
    assert repository.get_activation("ksw_absent") is None
    repository.upsert_activation(_record(switch_id="ksw_a", activated_at="2026-08-30T01:00:00Z"))
    repository.upsert_activation(_record(switch_id="ksw_b", activated_at="2026-08-30T02:00:00Z"))
    fetched = repository.get_activation("ksw_a")
    assert fetched is not None and fetched.switch_id == "ksw_a"
    assert [a.switch_id for a in repository.list_activations()] == ["ksw_b", "ksw_a"]


def test_sqlalchemy_repository_prepares_each_sqlite_location_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.repositories.sqlalchemy_kill_switch_repository import SqlAlchemyKillSwitchRepository

    SqlAlchemyKillSwitchRepository("sqlite:///:memory:").close()
    monkeypatch.chdir(tmp_path)
    SqlAlchemyKillSwitchRepository("sqlite:///data/nested/kill.db").close()
    assert (tmp_path / "data" / "nested").is_dir()
    SqlAlchemyKillSwitchRepository("postgresql+psycopg://user:secret@localhost:5432/db").close()


def test_store_accessor_fails_closed_on_bad_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "kill_switch_store_mode", "sqlalchemy")
    monkeypatch.setattr(settings, "database_url", None)
    with pytest.raises(RuntimeError, match="LOTUS_AI_DATABASE_URL is required"):
        get_kill_switch_repository()
    monkeypatch.setattr(settings, "kill_switch_store_mode", "carrier-pigeon")
    with pytest.raises(RuntimeError, match="Unsupported LOTUS_AI_KILL_SWITCH_STORE_MODE"):
        get_kill_switch_repository()


def test_scope_matcher_rejects_an_unknown_scope_object() -> None:
    from app.services.kill_switch_control import _matches

    bogus = KillSwitchActivationRecord.model_construct(
        switch_id="ksw_bogus",
        scope="NOT_A_SCOPE",
        target=None,
        reason="r",
        requested_by="a",
        approved_by="b",
        activated_at="2026-08-30T00:00:00Z",
        expires_at_utc=None,
        cleared_at=None,
        cleared_by=None,
        clear_reason=None,
    )
    with pytest.raises(RuntimeError, match="Unsupported kill-switch scope"):
        _matches(bogus, request=_provider_request())
