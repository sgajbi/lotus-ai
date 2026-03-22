from __future__ import annotations

from fastapi import APIRouter

from app.contracts.safety import SafetyPolicyResponse
from app.services.safety_policy import build_safety_policy

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
