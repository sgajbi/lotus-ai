"""The governed-action primitive (issue #157, slice 1).

Dual control binds to the signing credential: no verified human principal
exists in the identity model, so the enforceable fact is that two steps were
signed by two different credentials - a single compromised credential cannot
both request and approve. These tests pin that, the hash binding, and the
actor-class guards that keep the service-identity path from becoming the
approval bypass.
"""

import pytest
from fastapi import HTTPException

from app.contracts.governed_actions import (
    GovernedActionRecord,
    GovernedActionStatus,
    GovernedActionType,
    GovernedActorClass,
)
from app.http.authenticated_caller import AuthenticatedCaller
from app.services.governed_action_control import (
    approve_and_execute_governed_action,
    compute_governed_action_hash,
    record_system_originated_action,
    submit_governed_action,
)
from app.services.provider_operations_store import get_provider_operations_store

REQUESTER = AuthenticatedCaller(
    caller_app="lotus-platform",
    trust_source="verified_service_jwt",
    credential_key_id="ops-key-alpha",
)
APPROVER = AuthenticatedCaller(
    caller_app="lotus-platform",
    trust_source="verified_service_jwt",
    credential_key_id="ops-key-beta",
)
HEADER_CALLER = AuthenticatedCaller(
    caller_app="lotus-platform",
    trust_source="trusted_http_header",
    credential_key_id=None,
)

_PAYLOAD: dict[str, str | None] = {
    "action_type": "KILL_SWITCH_CLEAR",
    "switch_id": "ksw_test",
    "clear_reason": "incident resolved",
}


def _submit(**overrides: object) -> GovernedActionRecord:
    arguments: dict[str, object] = {
        "caller": REQUESTER,
        "action_type": GovernedActionType.KILL_SWITCH_CLEAR,
        "target": "ksw_test",
        "payload": dict(_PAYLOAD),
        "attribution": "ops.primary@lotus",
    }
    arguments.update(overrides)
    return submit_governed_action(**arguments)  # type: ignore[arg-type]


def _approve(record: GovernedActionRecord, **overrides: object) -> GovernedActionRecord:
    arguments: dict[str, object] = {
        "caller": APPROVER,
        "action_id": record.action_id,
        "expected_target": record.target,
        "expected_hash": record.action_hash,
        "current_payload_builder": lambda pending: dict(pending.action_payload),
        "attribution": "ops.secondary@lotus",
        "execute": lambda pending: None,
    }
    arguments.update(overrides)
    return approve_and_execute_governed_action(**arguments)  # type: ignore[arg-type]


def test_the_action_hash_is_canonical_and_order_independent() -> None:
    forward = compute_governed_action_hash({"a": "1", "b": None})
    reversed_keys = compute_governed_action_hash({"b": None, "a": "1"})
    assert forward == reversed_keys
    assert forward != compute_governed_action_hash({"a": "1", "b": "2"})


def test_request_and_distinct_approval_produce_complete_evidence() -> None:
    record = _submit()
    assert record.status is GovernedActionStatus.PENDING
    assert record.requester_key_id == "ops-key-alpha"
    assert record.approver_key_id is None

    executed = _approve(record)

    assert executed.status is GovernedActionStatus.EXECUTED
    assert executed.requester_key_id == "ops-key-alpha"
    assert executed.approver_key_id == "ops-key-beta"
    assert executed.approved_at is not None
    assert executed.executed_at is not None
    # The evidence is self-verifying: the stored payload reproduces the hash.
    assert compute_governed_action_hash(dict(executed.action_payload)) == executed.action_hash
    persisted = get_provider_operations_store().get_governed_action(record.action_id)
    assert persisted is not None
    assert persisted.status is GovernedActionStatus.EXECUTED


def test_the_same_credential_cannot_request_and_approve() -> None:
    record = _submit()
    with pytest.raises(HTTPException) as exc_info:
        _approve(record, caller=REQUESTER)
    assert exc_info.value.status_code == 403
    stored = get_provider_operations_store().get_governed_action(record.action_id)
    assert stored is not None
    assert stored.status is GovernedActionStatus.PENDING


def test_header_trust_cannot_participate_in_governed_actions() -> None:
    """Header trust carries no credential, so it cannot distinguish a
    requester from an approver - under it, dual control would be one
    anonymous party talking to itself."""

    with pytest.raises(HTTPException) as exc_info:
        _submit(caller=HEADER_CALLER)
    assert exc_info.value.status_code == 403

    record = _submit()
    with pytest.raises(HTTPException) as exc_info:
        _approve(record, caller=HEADER_CALLER)
    assert exc_info.value.status_code == 403


def test_approval_binds_to_the_exact_hash() -> None:
    record = _submit()
    with pytest.raises(HTTPException) as exc_info:
        _approve(record, expected_hash="0" * 64)
    assert exc_info.value.status_code == 409


def test_a_changed_action_is_not_approvable() -> None:
    """The freshness check: the payload is rebuilt from live domain state at
    approval time, so an approval reviewed against one action can never
    execute a different one."""

    record = _submit()
    changed = dict(_PAYLOAD, clear_reason="a different action entirely")
    with pytest.raises(HTTPException) as exc_info:
        _approve(record, current_payload_builder=lambda pending: changed)
    assert exc_info.value.status_code == 409
    assert "changed" in exc_info.value.detail


def test_an_approval_cannot_be_redirected_to_another_target() -> None:
    record = _submit()
    with pytest.raises(HTTPException) as exc_info:
        _approve(record, expected_target="ksw_other")
    assert exc_info.value.status_code == 409
    assert "cannot be redirected" in exc_info.value.detail


def test_a_new_request_supersedes_the_pending_one() -> None:
    first = _submit()
    second = _submit(payload=dict(_PAYLOAD, clear_reason="updated reason"))

    superseded = get_provider_operations_store().get_governed_action(first.action_id)
    assert superseded is not None
    assert superseded.status is GovernedActionStatus.SUPERSEDED
    assert superseded.superseded_by_action_id == second.action_id
    with pytest.raises(HTTPException) as exc_info:
        _approve(first)
    assert exc_info.value.status_code == 409
    assert _approve(second).status is GovernedActionStatus.EXECUTED


def test_a_failed_execution_leaves_the_claim_resumable_by_its_owner() -> None:
    """The atomic claim precedes the effect (issue #327): a failed execution
    leaves the action CLAIMED under the approver's evidence, resumable only by
    that credential - never silently re-approvable by anyone else."""

    record = _submit()

    def _explode(pending: object) -> None:
        raise RuntimeError("domain execution failed")

    with pytest.raises(RuntimeError):
        _approve(record, execute=_explode)
    stored = get_provider_operations_store().get_governed_action(record.action_id)
    assert stored is not None
    assert stored.status is GovernedActionStatus.CLAIMED
    assert stored.approver_key_id == APPROVER.credential_key_id
    assert stored.claimed_at is not None

    # A different verified credential cannot take over the claim.
    from types import SimpleNamespace

    other = SimpleNamespace(
        caller_app="operator-service",
        trust_source="verified_service_jwt",
        credential_key_id="key-other",
    )
    with pytest.raises(HTTPException) as exc_info:
        _approve(record, caller=other)
    assert exc_info.value.status_code == 409

    # The claiming credential resumes EXPLICITLY: the (idempotent) effect
    # re-runs and the action finalizes EXECUTED with the ORIGINAL claim
    # evidence preserved.
    effects: list[str] = []
    executed = _approve(
        record,
        execute=lambda pending: effects.append(pending.action_id),
        resume_interrupted_claim=True,
    )
    assert effects == [record.action_id]
    assert executed.status is GovernedActionStatus.EXECUTED
    assert executed.approver_key_id == APPROVER.credential_key_id
    assert executed.claimed_at == stored.claimed_at


def test_a_system_identity_cannot_originate_a_human_governed_action() -> None:
    """The actor class is explicit, never inferred from a service-looking
    string. A human-governed type refuses system origination outright, which
    is what stops the runtime path becoming the approval bypass."""

    with pytest.raises(HTTPException) as exc_info:
        record_system_originated_action(
            service_identity="lotus-ai.async-worker-runtime",
            action_type=GovernedActionType.KILL_SWITCH_CLEAR,
            target="ksw_test",
            payload=dict(_PAYLOAD),
        )
    assert exc_info.value.status_code == 403
    assert "human-governed" in exc_info.value.detail


def test_a_system_originated_record_would_have_no_approval_step() -> None:
    """Pinned at the primitive: even if a SYSTEM_ORIGINATED record reached the
    store for a human-governed type, approval refuses it - the actor-class
    guard does not depend on the creation guard alone."""

    record = _submit()
    forged = record.model_copy(update={"actor_class": GovernedActorClass.SYSTEM_ORIGINATED})
    get_provider_operations_store().upsert_governed_action(forged)
    with pytest.raises(HTTPException) as exc_info:
        _approve(forged)
    assert exc_info.value.status_code == 409
    assert "no approval step" in exc_info.value.detail


def test_a_system_originated_action_records_workload_identity_without_approval() -> None:
    """The legal system-originated path (issue #157, final slice): a runtime
    recovery action is recorded under the worker's workload identity with no
    approver, EXECUTED immediately - and, per the guard above, structurally
    incapable of ever satisfying a human-approval requirement."""

    record = record_system_originated_action(
        service_identity="worker-alpha-01",
        action_type=GovernedActionType.ASYNC_QUEUE_RECOVERY,
        target="asyncjob_recovered",
        payload={"action": "QUARANTINE_QUEUED_JOB", "reason": "poisoned payload"},
    )

    assert record.actor_class is GovernedActorClass.SYSTEM_ORIGINATED
    assert record.status is GovernedActionStatus.EXECUTED
    assert record.requester_caller_app == "worker-alpha-01"
    assert record.requester_key_id is None
    assert record.approver_caller_app is None
    assert record.approver_key_id is None
    persisted = get_provider_operations_store().get_governed_action(record.action_id)
    assert persisted == record


def test_governed_action_history_lists_newest_first_with_filters() -> None:
    """The read the approval flow presupposes (issue #157): pending actions
    are reviewable before approval, and the evidence chain is readable across
    every composing domain - with status and target filters."""

    from app.services.governed_action_control import build_governed_action_history

    pending = _submit()
    executed = record_system_originated_action(
        service_identity="worker-alpha-01",
        action_type=GovernedActionType.ASYNC_QUEUE_RECOVERY,
        target="asyncjob_listed",
        payload={"action": "QUARANTINE_QUEUED_JOB", "reason": "poisoned payload"},
    )

    everything = build_governed_action_history(REQUESTER)
    assert {record.action_id for record in everything.actions} == {
        pending.action_id,
        executed.action_id,
    }

    pending_only = build_governed_action_history(
        REQUESTER, status_filter=GovernedActionStatus.PENDING
    )
    assert [record.action_id for record in pending_only.actions] == [pending.action_id]
    # The pending record carries what the approver must review: the exact
    # payload and the hash approval binds to.
    assert pending_only.actions[0].action_hash == pending.action_hash
    assert pending_only.actions[0].action_payload == pending.action_payload

    targeted = build_governed_action_history(REQUESTER, target="asyncjob_listed")
    assert [record.action_id for record in targeted.actions] == [executed.action_id]

    assert build_governed_action_history(REQUESTER, target="no-such-target").actions == []


def test_governed_action_history_is_a_privileged_operator_read() -> None:
    """A registered Lotus caller is not automatically a control-plane operator
    (issue #157 correction): the read requires provider-control or
    prompt-control authorization, the denial is recorded on the
    privileged-access ledger before it is raised, and a successful read is
    recorded as all-tenant-class privileged access."""

    from app.contracts.audit_access import (
        AuditAccessDenialReason,
        AuditAccessOperation,
        AuditAccessOutcome,
    )
    from app.services.audit_store import get_audit_store
    from app.services.governed_action_control import build_governed_action_history

    _submit()

    # lotus-advise is registered and active, with no control capability.
    unauthorized = AuthenticatedCaller(
        caller_app="lotus-advise",
        trust_source="verified_service_jwt",
        credential_key_id="advise-key-01",
    )
    with pytest.raises(HTTPException) as exc_info:
        build_governed_action_history(unauthorized)
    assert exc_info.value.status_code == 403
    assert "control-plane operator capability" in exc_info.value.detail

    denied_events = [
        event
        for event in get_audit_store().list_access_events(limit=50)
        if event.operation is AuditAccessOperation.LIST_GOVERNED_ACTIONS
        and event.outcome is AuditAccessOutcome.DENIED
    ]
    assert len(denied_events) == 1
    assert denied_events[0].caller_app == "lotus-advise"
    assert denied_events[0].denial_reason is AuditAccessDenialReason.INSUFFICIENT_PRIVILEGE

    # The approver's own privilege (provider control on lotus-platform) reads,
    # and the successful privileged read is recorded with its record count.
    listed = build_governed_action_history(REQUESTER)
    assert len(listed.actions) == 1

    allowed_events = [
        event
        for event in get_audit_store().list_access_events(limit=50)
        if event.operation is AuditAccessOperation.LIST_GOVERNED_ACTIONS
        and event.outcome is AuditAccessOutcome.SUCCEEDED
    ]
    assert len(allowed_events) == 1
    assert allowed_events[0].caller_app == "lotus-platform"
    assert allowed_events[0].returned_record_count == 1


def test_approving_an_unknown_action_id_is_not_found() -> None:
    record = _submit()
    with pytest.raises(HTTPException) as exc_info:
        _approve(record, action_id="gact_does_not_exist")
    assert exc_info.value.status_code == 404


def test_losing_the_claim_race_refuses_without_running_the_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Issue #327: the atomic PENDING->CLAIMED claim IS the execution
    ownership. When a concurrent approval wins the transition between this
    approval's read and its compare-and-set, this approval refuses with 409
    and its domain callback never runs - the loser contributes no effect."""

    record = _submit()
    store = get_provider_operations_store()

    def claim_already_taken(
        *, action_id: str, expected_status: str, record: GovernedActionRecord
    ) -> bool:
        return False

    monkeypatch.setattr(store, "transition_governed_action", claim_already_taken)
    effects: list[str] = []
    with pytest.raises(HTTPException) as exc_info:
        _approve(record, execute=lambda pending: effects.append(pending.action_id))
    assert exc_info.value.status_code == 409
    assert "did not execute" in exc_info.value.detail
    assert effects == []


def test_a_claim_lost_during_execution_cannot_finalize_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Issue #327: EXECUTED evidence writes only over the caller's own live
    claim (CLAIMED->EXECUTED compare-and-set). If the claim is gone by
    finalization time, the domain effect has already run but the approval
    reports 409 instead of stamping evidence over state it no longer owns."""

    record = _submit()
    store = get_provider_operations_store()
    real_transition = store.transition_governed_action

    def stolen_after_execution(
        *, action_id: str, expected_status: str, record: GovernedActionRecord
    ) -> bool:
        if expected_status == GovernedActionStatus.CLAIMED.value:
            return False
        return real_transition(action_id=action_id, expected_status=expected_status, record=record)

    monkeypatch.setattr(store, "transition_governed_action", stolen_after_execution)
    effects: list[str] = []
    with pytest.raises(HTTPException) as exc_info:
        _approve(record, execute=lambda pending: effects.append(pending.action_id))
    assert exc_info.value.status_code == 409
    assert "could not be finalized" in exc_info.value.detail
    assert effects == [record.action_id]
