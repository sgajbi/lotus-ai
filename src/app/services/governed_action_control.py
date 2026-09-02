"""The governed-action primitive (issue #157, slice 1).

Domains compose three calls: ``submit_governed_action`` records a pending
intent under the requester's verified credential;
``approve_and_execute_governed_action`` validates a distinct verified
credential against the exact action hash, runs the domain's execute callback,
and persists the completed evidence; ``record_system_originated_action``
records a runtime action that answers to a service identity and is therefore
barred from every human-governed action type.

Persistence rides the provider-operations store rather than a new store seam:
that store already holds the cross-cutting operational control state (quota,
budget, degradation, control events), and one more mode setting, reset hook
and readiness probe would be exactly the proliferation the execution board
bans.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status

from app.contracts.governed_actions import (
    GovernedActionRecord,
    GovernedActionStatus,
    GovernedActionType,
    GovernedActorClass,
)
from app.http.authenticated_caller import AuthenticatedCaller
from app.services.provider_operations_store import get_provider_operations_store

# Action types where dual control applies: the action increases risk, so no
# single principal may carry it end to end. Safety-increasing actions never
# appear here - an emergency stop takes one verified principal, immediately.
HUMAN_GOVERNED_ACTION_TYPES = frozenset(
    {
        GovernedActionType.KILL_SWITCH_CLEAR,
        GovernedActionType.PROMPT_PROMOTE,
        GovernedActionType.PROVIDER_OPERATIONS_RESET,
        GovernedActionType.MODEL_LIFECYCLE_PROMOTE,
    }
)


def compute_governed_action_hash(payload: dict[str, str | None]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def submit_governed_action(
    *,
    caller: AuthenticatedCaller,
    action_type: GovernedActionType,
    target: str,
    payload: dict[str, str | None],
    attribution: str | None,
) -> GovernedActionRecord:
    """Record a pending intent under the requester's verified credential.

    A prior pending action for the same type and target is superseded rather
    than mutated: the old hash stops being approvable, and the supersession is
    itself evidence.
    """

    _require_verified_governing_credential(caller)
    repository = get_provider_operations_store()
    record = GovernedActionRecord(
        action_id=f"gact_{uuid4().hex[:16]}",
        action_type=action_type,
        actor_class=GovernedActorClass.HUMAN_APPROVED,
        status=GovernedActionStatus.PENDING,
        target=target,
        action_hash=compute_governed_action_hash(payload),
        action_payload=dict(payload),
        requester_caller_app=caller.caller_app,
        requester_trust_source=caller.trust_source,
        requester_key_id=caller.credential_key_id,
        requester_attribution=attribution,
        requested_at=_utc_now_iso(),
    )
    prior = repository.get_pending_governed_action(action_type=action_type.value, target=target)
    if prior is not None:
        repository.upsert_governed_action(
            prior.model_copy(
                update={
                    "status": GovernedActionStatus.SUPERSEDED,
                    "superseded_by_action_id": record.action_id,
                }
            )
        )
    repository.upsert_governed_action(record)
    return record


def approve_and_execute_governed_action(
    *,
    caller: AuthenticatedCaller,
    action_id: str,
    expected_target: str,
    expected_hash: str,
    current_payload_builder: Callable[[GovernedActionRecord], dict[str, str | None]],
    attribution: str | None,
    execute: Callable[[GovernedActionRecord], None],
) -> GovernedActionRecord:
    """Validate a distinct verified approver against the exact action, then execute.

    ``current_payload_builder`` rebuilds the action payload from the live
    domain state plus the pending record's own requested parameters; if the
    rebuilt hash no longer matches, the action changed between request and
    approval and the pending approval is not transferable to it.

    Everything is validated before the domain callback runs; the completed
    evidence (approver identity, approval and execution instants) persists in
    one write after the callback succeeds, so a failed execution leaves the
    action PENDING rather than half-approved.
    """

    _require_verified_governing_credential(caller)
    repository = get_provider_operations_store()
    record = repository.get_governed_action(action_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No governed action exists for `{action_id}`.",
        )
    if record.status is not GovernedActionStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Governed action `{action_id}` is {record.status.value}; only a PENDING "
                "action can be approved."
            ),
        )
    if record.actor_class is not GovernedActorClass.HUMAN_APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A system-originated action has no approval step.",
        )
    if record.target != expected_target:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Governed action `{action_id}` targets `{record.target}`, not "
                f"`{expected_target}`; an approval cannot be redirected."
            ),
        )
    if expected_hash != record.action_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The supplied action hash does not match the pending action. Approval binds "
                "to the exact action requested; review the pending action and approve its hash."
            ),
        )
    if compute_governed_action_hash(current_payload_builder(record)) != record.action_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The action has changed since it was requested. The pending approval is not "
                "transferable to the changed action; submit a new request."
            ),
        )
    if caller.credential_key_id == record.requester_key_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Approval requires a credential distinct from the requester's. The same "
                "signing credential cannot both request and approve a governed action."
            ),
        )

    execute(record)

    now = _utc_now_iso()
    executed = record.model_copy(
        update={
            "status": GovernedActionStatus.EXECUTED,
            "approver_caller_app": caller.caller_app,
            "approver_trust_source": caller.trust_source,
            "approver_key_id": caller.credential_key_id,
            "approver_attribution": attribution,
            "approved_at": now,
            "executed_at": now,
        }
    )
    repository.upsert_governed_action(executed)
    return executed


def record_system_originated_action(
    *,
    service_identity: str,
    action_type: GovernedActionType,
    target: str,
    payload: dict[str, str | None],
) -> GovernedActionRecord:
    """Record a runtime action that answers to a service identity.

    A system-originated action is explicitly system-originated: it carries no
    approver, cannot satisfy a human four-eyes requirement, and is refused
    outright for human-governed action types - which is what stops the
    service-identity path becoming the approval bypass.
    """

    if action_type in HUMAN_GOVERNED_ACTION_TYPES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"`{action_type.value}` is a human-governed action type; a system identity "
                "cannot originate or approve it."
            ),
        )
    record = GovernedActionRecord(
        action_id=f"gact_{uuid4().hex[:16]}",
        action_type=action_type,
        actor_class=GovernedActorClass.SYSTEM_ORIGINATED,
        status=GovernedActionStatus.EXECUTED,
        target=target,
        action_hash=compute_governed_action_hash(payload),
        action_payload=dict(payload),
        requester_caller_app=service_identity,
        requester_trust_source="service_runtime",
        requested_at=_utc_now_iso(),
        executed_at=_utc_now_iso(),
    )
    get_provider_operations_store().upsert_governed_action(record)
    return record


def _require_verified_governing_credential(caller: AuthenticatedCaller) -> None:
    """Both steps of a governed action require a verified signing credential.

    Header trust carries no credential at all, so it cannot distinguish two
    principals - under it, dual control would be one anonymous party talking
    to itself. Refusing outright is honest; treating it as a weaker principal
    would make the guarantee unverifiable.
    """

    if not caller.credential_key_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Governed actions require a verified caller credential; header-trusted "
                "identity cannot distinguish a requester from an approver."
            ),
        )


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()
