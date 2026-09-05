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

from app.config import settings
from app.contracts.governed_actions import (
    GovernedActionHistoryResponse,
    GovernedActionRecord,
    GovernedActionStatus,
    GovernedActionType,
    GovernedActorClass,
)
from app.contracts.access_control import AuthorizationCapabilityType
from app.contracts.audit_access import AuditAccessDenialReason, AuditAccessOperation
from app.http.authenticated_caller import AuthenticatedCaller
from app.services.access_control_authorization import authorize_request
from app.services.audit_read_authorization import (
    record_privileged_read,
    refuse_privileged_read,
)
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
        GovernedActionType.MODEL_CAPABILITY_RESTORE,
        GovernedActionType.DATA_ERASURE,
        GovernedActionType.SERVING_POLICY_IDENTITY_ADD,
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
        # Guarded transition (issue #327): if the prior action was claimed or
        # executed concurrently, supersession loses and that execution stands;
        # this new request still records as the next pending intent.
        repository.transition_governed_action(
            action_id=prior.action_id,
            expected_status=GovernedActionStatus.PENDING.value,
            record=prior.model_copy(
                update={
                    "status": GovernedActionStatus.SUPERSEDED,
                    "superseded_by_action_id": record.action_id,
                }
            ),
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
    result_payload_builder: Callable[[], dict[str, object]] | None = None,
    resume_interrupted_claim: bool = False,
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
    # Resuming an interrupted claim is an EXPLICIT recovery intent, never an
    # inference: a live claim raced by its own credential must refuse, or two
    # same-credential approvals would both run the effect (issue #327).
    resuming_own_claim = (
        resume_interrupted_claim
        and record.status is GovernedActionStatus.CLAIMED
        and record.approver_key_id == caller.credential_key_id
    )
    if record.status is not GovernedActionStatus.PENDING and not resuming_own_claim:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Governed action `{action_id}` is {record.status.value}; only a PENDING "
                "action (or the claiming credential resuming its own interrupted claim) "
                "can be approved."
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

    now = _utc_now_iso()
    if resuming_own_claim:
        claimed = record
    else:
        claimed = record.model_copy(
            update={
                "status": GovernedActionStatus.CLAIMED,
                "approver_caller_app": caller.caller_app,
                "approver_trust_source": caller.trust_source,
                "approver_key_id": caller.credential_key_id,
                "approver_attribution": attribution,
                "approved_at": now,
                "claimed_at": now,
            }
        )
        # The atomic claim IS the transition ownership (issue #327): exactly
        # one approval session moves PENDING to CLAIMED; a concurrent
        # approval, supersession or execution makes this a refusal, never a
        # second effect.
        if not repository.transition_governed_action(
            action_id=action_id,
            expected_status=GovernedActionStatus.PENDING.value,
            record=claimed,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Governed action `{action_id}` was claimed, superseded or executed "
                    "concurrently; this approval did not execute."
                ),
            )

    # The callback contract (issue #327): domain effects must be idempotent
    # under the governed action identity - a crash between the claim and the
    # EXECUTED write is recovered by the claiming credential re-approving,
    # which re-invokes the callback.
    execute(claimed)

    executed = claimed.model_copy(
        update={
            "status": GovernedActionStatus.EXECUTED,
            "executed_at": _utc_now_iso(),
            "result_payload": (
                result_payload_builder() if result_payload_builder is not None else None
            ),
        }
    )
    if not repository.transition_governed_action(
        action_id=action_id,
        expected_status=GovernedActionStatus.CLAIMED.value,
        record=executed,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Governed action `{action_id}` left its claim while executing; the "
                "domain effect ran but the execution evidence could not be finalized."
            ),
        )
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


_GOVERNED_ACTION_READ_CAPABILITIES = (
    AuthorizationCapabilityType.PROVIDER_CONTROL,
    AuthorizationCapabilityType.PROMPT_CONTROL,
)


def _require_governed_action_read_authorization(caller: AuthenticatedCaller) -> None:
    """The governed-action ledger is control-plane operator evidence.

    Pending payloads and hashes, requester and approver identities: a
    registered Lotus caller is not automatically an AI control-plane
    operator. The read requires one of the control capabilities whose
    actions the ledger records - exactly the privilege an approver already
    holds - and every refusal is recorded on the privileged-access ledger
    before it is raised.
    """

    for capability in _GOVERNED_ACTION_READ_CAPABILITIES:
        decision = authorize_request(caller_app=caller.caller_app, capability_type=capability)
        if decision.allowed:
            return
    refuse_privileged_read(
        caller,
        operation=AuditAccessOperation.LIST_GOVERNED_ACTIONS,
        reason=AuditAccessDenialReason.INSUFFICIENT_PRIVILEGE,
        detail=(
            "Reading governed-action evidence requires a control-plane operator "
            "capability (provider control or prompt control)."
        ),
    )


def build_governed_action_history(
    caller: AuthenticatedCaller,
    *,
    status_filter: GovernedActionStatus | None = None,
    target: str | None = None,
    limit: int = 50,
) -> GovernedActionHistoryResponse:
    """Read governed-action evidence, newest requested first (issue #157).

    A privileged read over the existing store: the approver reviews the exact
    pending action before approving its hash, and the auditor reconstructs
    the request-approval-execution chain - including evidence pinned only
    here, such as a capability degradation cleared by an executed restore.
    Denied and successful reads both land on the privileged-access ledger.
    """

    _require_governed_action_read_authorization(caller)
    records = get_provider_operations_store().list_governed_actions(
        status=status_filter.value if status_filter is not None else None,
        target=target,
        limit=limit,
    )
    record_privileged_read(
        caller,
        operation=AuditAccessOperation.LIST_GOVERNED_ACTIONS,
        returned_record_count=len(records),
    )
    return GovernedActionHistoryResponse(
        service=settings.service_name,
        version=settings.service_version,
        actions=records,
    )


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()
