from __future__ import annotations

from fastapi import APIRouter

from app.contracts.safety import SafetyPolicyResponse, SafetyRuntimeStatusResponse
from app.services.safety_policy import build_safety_policy
from app.services.safety_status import build_safety_runtime_status

router = APIRouter(prefix="/platform/safety", tags=["platform"])


@router.get(
    "/policy",
    response_model=SafetyPolicyResponse,
    operation_id="getSafetyPolicy",
    summary="Get lotus-ai safety policy",
    description=(
        "Returns the governed lotus-ai safety posture, including control status and task-level "
        "output-label and redaction guidance."
    ),
    responses={
        200: {"description": "Safety policy returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_safety_policy_route() -> SafetyPolicyResponse:
    return build_safety_policy()


@router.get(
    "/runtime-status",
    response_model=SafetyRuntimeStatusResponse,
    operation_id="getSafetyRuntimeStatus",
    summary="Get lotus-ai safety runtime status",
    description=(
        "Returns the current runtime safety posture for lotus-ai, including which controls are "
        "enforced today and whether any runtime redaction engine is active."
    ),
    responses={
        200: {"description": "Safety runtime status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_safety_runtime_status_route() -> SafetyRuntimeStatusResponse:
    return build_safety_runtime_status()
