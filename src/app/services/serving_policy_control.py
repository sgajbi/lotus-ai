"""The governed serving-policy artifact (issue #295, S2).

The ordered identities that may serve become a stored, versioned policy over
catalogue entries — the #244 U3 recorded decision, unblocked by S1's
connection-material generalisation. Direction decides governance, exactly as
the steering ordered:

- **adding** an identity widens what may serve: risk-increasing, so it takes
  the #157 two-step primitive — a verified requester states the intent, a
  DISTINCT verified credential approves the exact resulting order (a policy
  change between request and approval changes the rebuilt hash and refuses
  the stale approval);
- **removing** an identity is risk-reducing: one verified principal,
  immediate, ``approver_key_id`` honestly null — the kill-switch safety
  direction.

Order is policy, never ranking: no weights, no optimizer, no cost- or
latency-based reordering. Every version records who changed it and, for
additions, the governed-action evidence reference.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.access_control import AuthorizationCapabilityType
from app.contracts.governed_actions import (
    GovernedActionRecord,
    GovernedActionResponse,
    GovernedActionType,
)
from app.contracts.model_catalogue import (
    ServingPolicyChangeResponse,
    ServingPolicyIdentityAddApprovalRequest,
    ServingPolicyIdentityAddRequest,
    ServingPolicyIdentityRemovalRequest,
    ServingPolicyStatusResponse,
    ServingPolicyVersionRecord,
)
from app.http.authenticated_caller import AuthenticatedCaller
from app.services.access_control_authorization import authorize_request, require_authorized
from app.services.governed_action_control import (
    approve_and_execute_governed_action,
    submit_governed_action,
)
from app.services.kill_switch_control import verified_caller_identity
from app.services.model_catalogue import (
    _EXECUTION_INELIGIBLE_LIFECYCLE_STATES,
    current_serving_order,
    ensure_model_catalogue_seeded,
)
from app.services.model_catalogue_store import get_model_catalogue_repository

_VERSION_HISTORY_LIMIT = 50


def _require_provider_control(caller: AuthenticatedCaller) -> None:
    require_authorized(
        authorize_request(
            caller_app=caller.caller_app,
            capability_type=AuthorizationCapabilityType.PROVIDER_CONTROL,
        )
    )


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def build_serving_policy_status() -> ServingPolicyStatusResponse:
    repository = get_model_catalogue_repository()
    current = repository.get_current_serving_policy()
    return ServingPolicyStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        current=current,
        versions=repository.list_serving_policy_versions(limit=_VERSION_HISTORY_LIMIT),
        summary=[
            (
                f"Serving order follows policy version {current.version}."
                if current is not None
                else "No serving-policy artifact exists yet; ordering follows the "
                "configured primary/fallback pair."
            ),
            "Adding an identity is governed two-step; removal is immediate by one "
            "verified principal.",
        ],
    )


def _add_payload(
    *, entry_id: str, reason: str, resulting_order: list[str]
) -> dict[str, str | None]:
    """The exact change the approver signs off on: the identity AND the full
    resulting order, so an approval reviewed against one order can never
    execute against another."""

    return {
        "action_type": GovernedActionType.SERVING_POLICY_IDENTITY_ADD.value,
        "entry_id": entry_id,
        "reason": reason,
        "resulting_order": ",".join(resulting_order),
    }


def request_serving_policy_identity_add(
    request: ServingPolicyIdentityAddRequest, caller: AuthenticatedCaller
) -> GovernedActionResponse:
    _require_provider_control(caller)
    ensure_model_catalogue_seeded()
    entry = get_model_catalogue_repository().get_entry(request.entry_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No governed catalogue entry exists for `{request.entry_id}`.",
        )
    if entry.lifecycle_state in _EXECUTION_INELIGIBLE_LIFECYCLE_STATES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"`{request.entry_id}` is {entry.lifecycle_state.value} and not eligible to "
                "serve; promote it through the governed lifecycle before adding it to the "
                "serving policy."
            ),
        )
    order, _ = current_serving_order()
    if request.entry_id in order:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"`{request.entry_id}` is already in the serving order.",
        )
    record = submit_governed_action(
        caller=caller,
        action_type=GovernedActionType.SERVING_POLICY_IDENTITY_ADD,
        target=request.entry_id,
        payload=_add_payload(
            entry_id=request.entry_id,
            reason=request.reason,
            resulting_order=[*order, request.entry_id],
        ),
        attribution=request.requested_by,
    )
    return GovernedActionResponse(
        service=settings.service_name,
        version=settings.service_version,
        governed_action=record,
        summary=[
            f"Adding `{request.entry_id}` to the serving order is pending approval.",
            "A distinct verified credential must approve action "
            f"`{record.action_id}` with hash `{record.action_hash}`.",
            "The hash binds the full resulting order: a policy change before approval "
            "refuses the stale approval.",
        ],
    )


def approve_serving_policy_identity_add(
    request: ServingPolicyIdentityAddApprovalRequest, caller: AuthenticatedCaller
) -> ServingPolicyChangeResponse:
    _require_provider_control(caller)
    saved: dict[str, ServingPolicyVersionRecord] = {}

    def _execute(record: GovernedActionRecord) -> None:
        order, version = current_serving_order()
        new_version = ServingPolicyVersionRecord(
            version=(version or 0) + 1,
            ordered_entry_ids=[*order, record.target],
            action="IDENTITY_ADD",
            changed_entry_id=record.target,
            requested_by_key_id=record.requester_key_id or "unknown",
            approver_key_id=caller.credential_key_id,
            governed_action_id=record.action_id,
            recorded_at=_utc_now_iso(),
        )
        get_model_catalogue_repository().save_serving_policy_version(new_version)
        saved["policy"] = new_version

    executed = approve_and_execute_governed_action(
        caller=caller,
        action_id=request.action_id,
        expected_target=_approval_target(request.action_id),
        expected_hash=request.action_hash,
        current_payload_builder=lambda record: _add_payload(
            entry_id=record.target,
            reason=str(record.action_payload.get("reason")),
            resulting_order=[*current_serving_order()[0], record.target],
        ),
        attribution=request.approved_by,
        execute=_execute,
    )
    policy = saved["policy"]
    return ServingPolicyChangeResponse(
        service=settings.service_name,
        version=settings.service_version,
        policy=policy,
        summary=[
            f"Serving policy version {policy.version} is operative: `{executed.target}` may "
            "now serve, in governed order.",
            f"Requested under credential `{executed.requester_key_id}` and approved under "
            f"distinct credential `{executed.approver_key_id}`.",
        ],
    )


def _approval_target(action_id: str) -> str:
    from app.services.provider_operations_store import get_provider_operations_store

    record = get_provider_operations_store().get_governed_action(action_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No governed action exists for `{action_id}`.",
        )
    return record.target


def remove_serving_policy_identity(
    request: ServingPolicyIdentityRemovalRequest, caller: AuthenticatedCaller
) -> ServingPolicyChangeResponse:
    """Risk-reducing, so the safety direction applies: one verified principal
    acts immediately, and the version records ``approver_key_id`` as null
    rather than dressing anyone up as a second approver."""

    _require_provider_control(caller)
    order, version = current_serving_order()
    if request.entry_id not in order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"`{request.entry_id}` is not in the serving order.",
        )
    new_version = ServingPolicyVersionRecord(
        version=(version or 0) + 1,
        ordered_entry_ids=[entry for entry in order if entry != request.entry_id],
        action="IDENTITY_REMOVE",
        changed_entry_id=request.entry_id,
        requested_by_key_id=(caller.credential_key_id or verified_caller_identity(caller)),
        approver_key_id=None,
        governed_action_id=None,
        recorded_at=_utc_now_iso(),
    )
    get_model_catalogue_repository().save_serving_policy_version(new_version)
    return ServingPolicyChangeResponse(
        service=settings.service_name,
        version=settings.service_version,
        policy=new_version,
        summary=[
            f"Serving policy version {new_version.version} is operative: "
            f"`{request.entry_id}` no longer serves.",
            "Removal is the risk-reducing direction: recorded under one verified "
            "principal with no second approver, immediately.",
            f"Reason: {request.reason}",
        ],
    )
