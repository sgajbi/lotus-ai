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


def test_a_failed_execution_leaves_the_action_pending() -> None:
    record = _submit()

    def _explode(pending: object) -> None:
        raise RuntimeError("domain execution failed")

    with pytest.raises(RuntimeError):
        _approve(record, execute=_explode)
    stored = get_provider_operations_store().get_governed_action(record.action_id)
    assert stored is not None
    assert stored.status is GovernedActionStatus.PENDING
    assert stored.approver_key_id is None


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
