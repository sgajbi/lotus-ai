from __future__ import annotations

from fastapi import APIRouter

from app.contracts.kill_switches import (
    KillSwitchActionResponse,
    KillSwitchActivationRequest,
    KillSwitchClearRequest,
    KillSwitchStatusResponse,
)
from app.services.kill_switch_control import (
    activate_kill_switch,
    build_kill_switch_status,
    clear_kill_switch,
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
    "/{switch_id}/clear",
    response_model=KillSwitchActionResponse,
    operation_id="clearKillSwitch",
    summary="Clear a kill switch",
    description=(
        "Clears one kill-switch activation so matching live executions may resume. Requires "
        "provider-control authorization, requester and approver identity, and an operator "
        "reason; the activation and its clearance remain durably recorded."
    ),
    responses={
        200: {"description": "Kill switch cleared."},
        403: {"description": "Caller is not authorized for provider control."},
        404: {"description": "No activation exists for the given switch id."},
        409: {"description": "The activation is already cleared, or the store is not durable."},
        500: {"description": "Unexpected server error."},
    },
)
async def clear_kill_switch_route(
    switch_id: str, request: KillSwitchClearRequest
) -> KillSwitchActionResponse:
    return clear_kill_switch(switch_id, request)
