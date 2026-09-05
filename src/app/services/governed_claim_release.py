"""Governed release of a frozen claim (issue #340).

A CLAIMED action whose credential disappears stays frozen by design: resume
requires the claiming credential, supersession loses to a live claim, and no
timeout exists - a lease expiring under a slow executor would re-open the
two-owner window #327 closed. This is the explicit operator path out: a
four-eyes CLAIM_RELEASE action whose requester AND approver must BOTH differ
from the frozen claim's credential (three distinct credentials total), whose
payload pins the target's hash, claim instant and frozen credential at
request time, and whose execution is a compare-and-set CLAIMED->PENDING on
the SAME claim-instant fence resume rotates on - a release racing the
original owner's resume admits exactly one winner by construction.

Safety argument for the maybe-already-ran effect: the target's effect may
have completed before its EXECUTED write was lost. Re-approval after release
re-invokes a callback contracted idempotent under the ACTION identity, so
the outcome converges (erasure: deterministic per-family event merge;
reconciliation: guarded CAS no-op). Explicitly rejected alternatives:
TTL/lease auto-release, direct store edits (no evidence), and
release-and-execute in one step (collapses four-eyes to two).
"""

from __future__ import annotations

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.governed_actions import (
    ClaimReleaseApprovalRequest,
    ClaimReleaseApprovalResponse,
    ClaimReleaseIntentRequest,
    GovernedActionRecord,
    GovernedActionResponse,
    GovernedActionStatus,
    GovernedActionType,
)
from app.http.authenticated_caller import AuthenticatedCaller
from app.services.access_control_authorization import authorize_request, require_authorized
from app.contracts.access_control import AuthorizationCapabilityType
from app.services.governed_action_control import (
    approve_and_execute_governed_action,
    submit_governed_action,
)
from app.services.provider_operations_store import get_provider_operations_store


def _require_provider_control_authorization(caller: AuthenticatedCaller) -> None:
    require_authorized(
        authorize_request(
            caller_app=caller.caller_app,
            capability_type=AuthorizationCapabilityType.PROVIDER_CONTROL,
        )
    )


def _release_payload(
    *,
    target_action_id: str,
    target_action_hash: str,
    target_claimed_at: str,
    frozen_approver_key_id: str,
    reason: str,
) -> dict[str, str | None]:
    """The exact action the approver signs off on: the frozen claim's full
    identity at request time. A target that resumed, finalized, or changed
    hands rebuilds to a different payload and refuses."""

    return {
        "action_type": GovernedActionType.CLAIM_RELEASE.value,
        "target_action_id": target_action_id,
        "target_action_hash": target_action_hash,
        "target_claimed_at": target_claimed_at,
        "frozen_approver_key_id": frozen_approver_key_id,
        "reason": reason,
    }


def _refuse_frozen_credential(caller: AuthenticatedCaller, frozen_key_id: str | None) -> None:
    if caller.credential_key_id is not None and caller.credential_key_id == frozen_key_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "The frozen claim's own credential cannot participate in its "
                "release; it already holds the resume path. Release requires "
                "two credentials distinct from the claim holder's."
            ),
        )


def request_claim_release(
    request: ClaimReleaseIntentRequest, caller: AuthenticatedCaller
) -> GovernedActionResponse:
    """Step one: record the release intent under a verified credential that
    is NOT the frozen claim holder."""

    _require_provider_control_authorization(caller)
    store = get_provider_operations_store()
    target = store.get_governed_action(request.target_action_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No governed action exists for `{request.target_action_id}`.",
        )
    if target.status is not GovernedActionStatus.CLAIMED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Governed action `{request.target_action_id}` is "
                f"{target.status.value}; only a CLAIMED action releases."
            ),
        )
    _refuse_frozen_credential(caller, target.approver_key_id)
    assert target.claimed_at is not None and target.approver_key_id is not None
    record = submit_governed_action(
        caller=caller,
        action_type=GovernedActionType.CLAIM_RELEASE,
        target=request.target_action_id,
        payload=_release_payload(
            target_action_id=request.target_action_id,
            target_action_hash=target.action_hash,
            target_claimed_at=target.claimed_at,
            frozen_approver_key_id=target.approver_key_id,
            reason=request.reason,
        ),
        attribution=request.requested_by,
    )
    return GovernedActionResponse(
        service=settings.service_name,
        version=settings.service_version,
        governed_action=record,
        summary=[
            f"Release of the claim on `{request.target_action_id}` (held by credential "
            f"`{target.approver_key_id}` since {target.claimed_at}) is pending approval.",
            "A verified credential DISTINCT from both the requester and the claim "
            f"holder must approve action `{record.action_id}` with hash "
            f"`{record.action_hash}`.",
            "Nothing changes on the target until the approval executes; the frozen "
            "credential's own resume path stays available and wins any race by "
            "compare-and-set.",
        ],
    )


def approve_claim_release(
    request: ClaimReleaseApprovalRequest, caller: AuthenticatedCaller
) -> ClaimReleaseApprovalResponse:
    """Step two: a third distinct credential approves; execution releases the
    claim back to PENDING with the release evidence durable."""

    _require_provider_control_authorization(caller)
    store = get_provider_operations_store()

    existing = store.get_governed_action(request.action_id)
    if (
        existing is not None
        and existing.status is GovernedActionStatus.EXECUTED
        and existing.action_hash == request.action_hash
        and existing.result_payload is not None
    ):
        return _release_response_from_result(existing)
    if existing is not None:
        _refuse_frozen_credential(
            caller, str(existing.action_payload.get("frozen_approver_key_id"))
        )

    def _rebuild_payload(record: GovernedActionRecord) -> dict[str, str | None]:
        target_id = str(record.action_payload.get("target_action_id"))
        target = store.get_governed_action(target_id)
        if (
            target is None
            or target.status is not GovernedActionStatus.CLAIMED
            or target.claimed_at is None
            or target.approver_key_id is None
        ):
            # A resumed, finalized, or vanished target rebuilds to a payload
            # that cannot match the pinned one - the 409 says the action
            # changed, which is the truth.
            return {
                "action_type": GovernedActionType.CLAIM_RELEASE.value,
                "target_action_id": target_id,
                "target_action_hash": "TARGET_NO_LONGER_CLAIMED",
                "target_claimed_at": None,
                "frozen_approver_key_id": None,
                "reason": str(record.action_payload.get("reason")),
            }
        return _release_payload(
            target_action_id=target_id,
            target_action_hash=target.action_hash,
            target_claimed_at=target.claimed_at,
            frozen_approver_key_id=target.approver_key_id,
            reason=str(record.action_payload.get("reason")),
        )

    released_holder: dict[str, GovernedActionRecord] = {}

    def _execute_release(record: GovernedActionRecord) -> None:
        target_id = str(record.action_payload.get("target_action_id"))
        pinned_claimed_at = str(record.action_payload.get("target_claimed_at"))
        target = store.get_governed_action(target_id)
        if target is None or target.status is not GovernedActionStatus.CLAIMED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"The claim on `{target_id}` moved before the release executed; "
                    "nothing was changed."
                ),
            )
        released = target.model_copy(
            update={
                "status": GovernedActionStatus.PENDING,
                "approver_caller_app": None,
                "approver_trust_source": None,
                "approver_key_id": None,
                "approver_attribution": None,
                "approved_at": None,
                "claimed_at": None,
            }
        )
        # The release races resume and finalization on the SAME fence they
        # use: the pinned claim instant. Exactly one wins.
        if not store.transition_governed_action(
            action_id=target_id,
            expected_status=GovernedActionStatus.CLAIMED.value,
            record=released,
            expected_claimed_at=pinned_claimed_at,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"The claim on `{target_id}` changed hands while the release "
                    "executed (a resume or finalization won); nothing was changed."
                ),
            )
        released_holder["released"] = released

    executed = approve_and_execute_governed_action(
        caller=caller,
        action_id=request.action_id,
        expected_target=_expected_target(request),
        expected_hash=request.action_hash,
        current_payload_builder=_rebuild_payload,
        attribution=request.approved_by,
        execute=_execute_release,
        result_payload_builder=lambda: {
            "released_target_action_id": released_holder["released"].action_id,
            "frozen_approver_key_id": str(
                (existing.action_payload if existing else {}).get("frozen_approver_key_id")
            ),
            "reason": str((existing.action_payload if existing else {}).get("reason")),
        },
        resume_interrupted_claim=request.resume_interrupted_claim,
    )
    released = released_holder["released"]
    return ClaimReleaseApprovalResponse(
        service=settings.service_name,
        version=settings.service_version,
        governed_action=executed,
        released_action=released,
        summary=[
            f"The claim on `{released.action_id}` is released: the action is PENDING "
            "again with its requester evidence intact.",
            "The prior effect may have run; re-approval re-invokes a callback that is "
            "idempotent under the action identity, so the outcome converges.",
            f"Release requested under `{executed.requester_key_id}` and approved under "
            f"distinct credential `{executed.approver_key_id}` - both distinct from "
            "the frozen claim holder.",
        ],
    )


def _expected_target(request: ClaimReleaseApprovalRequest) -> str:
    record = get_provider_operations_store().get_governed_action(request.action_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No governed action exists for `{request.action_id}`.",
        )
    return record.target


def _release_response_from_result(record: GovernedActionRecord) -> ClaimReleaseApprovalResponse:
    payload = record.result_payload or {}
    target_id = str(payload.get("released_target_action_id"))
    target = get_provider_operations_store().get_governed_action(target_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"The released action `{target_id}` no longer exists.",
        )
    return ClaimReleaseApprovalResponse(
        service=settings.service_name,
        version=settings.service_version,
        governed_action=record,
        released_action=target,
        summary=[
            f"The claim on `{target_id}` was already released by this executed action; "
            "this is the recorded outcome, not a second release.",
        ],
    )
