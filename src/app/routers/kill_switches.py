from __future__ import annotations

from fastapi import APIRouter

from app.contracts.governed_actions import GovernedActionResponse
from app.contracts.kill_switches import (
    KillSwitchActionResponse,
    KillSwitchActivationRequest,
    KillSwitchClearApprovalRequest,
    KillSwitchClearApprovalResponse,
    KillSwitchClearIntentRequest,
    KillSwitchStatusResponse,
)
from app.http.authenticated_caller import AuthenticatedCallerDependency
from app.services.kill_switch_control import (
    activate_kill_switch,
    approve_kill_switch_clearance,
    build_kill_switch_status,
    request_kill_switch_clearance,
)

router = APIRouter(prefix="/platform/providers/kill-switches", tags=["platform"])


@router.get(
    "",
    response_model=KillSwitchStatusResponse,
    operation_id="getKillSwitchStatus",
    summary="List kill-switch activations",
    description=(
        "Returns every recorded kill-switch activation - currently enforcing, expired, and "
        "cleared - with the enforcing count, so operators can inspect the live kill posture."
    ),
    responses={
        200: {"description": "Kill-switch status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_kill_switch_status_route() -> KillSwitchStatusResponse:
    return build_kill_switch_status()


@router.post(
    "",
    response_model=KillSwitchActionResponse,
    operation_id="activateKillSwitch",
    summary="Activate a kill switch",
    description=(
        "Activates a scoped kill switch. HARD_KILL (default) refuses all matching live "
        "execution immediately; DRAIN refuses new synchronous executions and new async "
        "intake while already-claimed async workflow-pack jobs complete safely. Refusals "
        "carry the bounded KILL_SWITCH_ACTIVE category and a recorded routing rejection. "
        "Requires provider-control authorization, requester and approver identity, an "
        "operator reason, and the durable kill-switch store."
    ),
    responses={
        200: {"description": "Kill switch activated."},
        403: {"description": "Caller is not authorized for provider control."},
        409: {"description": "The durable kill-switch store is not configured."},
        422: {"description": "The activation request is invalid for its scope."},
        500: {"description": "Unexpected server error."},
    },
)
async def activate_kill_switch_route(
    request: KillSwitchActivationRequest,
) -> KillSwitchActionResponse:
    return activate_kill_switch(request)


@router.post(
    "/{switch_id}/clear-requests",
    response_model=GovernedActionResponse,
    operation_id="requestKillSwitchClearance",
    summary="Request clearance of a kill switch",
    description=(
        "Step one of governed clearance (issue #157): records a pending clear intent under "
        "the requester's verified credential and returns the action hash a distinct verified "
        "credential must approve. The switch keeps enforcing until the approval executes."
    ),
    responses={
        200: {"description": "Clearance intent recorded and pending approval."},
        403: {
            "description": "Caller is not authorized for provider control, or carries no "
            "verified credential."
        },
        404: {"description": "No activation exists for the given switch id."},
        409: {"description": "The activation is already cleared, or the store is not durable."},
        500: {"description": "Unexpected server error."},
    },
)
async def request_kill_switch_clearance_route(
    switch_id: str,
    request: KillSwitchClearIntentRequest,
    authenticated_caller: AuthenticatedCallerDependency,
) -> GovernedActionResponse:
    return request_kill_switch_clearance(switch_id, request, authenticated_caller)


@router.post(
    "/{switch_id}/clear-approvals",
    response_model=KillSwitchClearApprovalResponse,
    operation_id="approveKillSwitchClearance",
    summary="Approve and execute a pending kill-switch clearance",
    description=(
        "Step two of governed clearance (issue #157): a verified credential DISTINCT from "
        "the requester's approves the exact pending action hash, which clears the switch and "
        "records the full request-approval-execution evidence chain."
    ),
    responses={
        200: {"description": "Kill switch cleared under governed approval."},
        403: {
            "description": "Caller is not authorized, carries no verified credential, or is "
            "the same credential that requested the clearance."
        },
        404: {"description": "No activation or pending action exists."},
        409: {
            "description": "The action hash does not match, the action changed since it was "
            "requested, the action is not pending, or the store is not durable."
        },
        500: {"description": "Unexpected server error."},
    },
)
async def approve_kill_switch_clearance_route(
    switch_id: str,
    request: KillSwitchClearApprovalRequest,
    authenticated_caller: AuthenticatedCallerDependency,
) -> KillSwitchClearApprovalResponse:
    return approve_kill_switch_clearance(switch_id, request, authenticated_caller)
