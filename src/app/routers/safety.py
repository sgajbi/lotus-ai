from __future__ import annotations

from fastapi import APIRouter

from app.contracts.safety import (
    SafetyEvidenceReadinessResponse,
    SafetyGovernanceStatusResponse,
    SafetyPolicyResponse,
    SafetyRunbookReadinessResponse,
    SafetyRuntimeStatusResponse,
)
from app.services.safety_evidence_readiness import build_safety_evidence_readiness
from app.services.safety_governance_status import build_safety_governance_status
from app.services.safety_policy import build_safety_policy
from app.services.safety_runbook_readiness import build_safety_runbook_readiness
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


@router.get(
    "/evidence-readiness",
    response_model=SafetyEvidenceReadinessResponse,
    operation_id="getSafetyEvidenceReadiness",
    summary="Get lotus-ai safety evidence readiness",
    description=(
        "Returns the current runtime-backed evaluation and audit evidence posture for safety enforcement."
    ),
    responses={
        200: {"description": "Safety evidence readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_safety_evidence_readiness_route() -> SafetyEvidenceReadinessResponse:
    return build_safety_evidence_readiness()


@router.get(
    "/runbook-readiness",
    response_model=SafetyRunbookReadinessResponse,
    operation_id="getSafetyRunbookReadiness",
    summary="Get lotus-ai safety runbook readiness",
    description=(
        "Returns the current operational runbook readiness posture for runtime safety enforcement."
    ),
    responses={
        200: {"description": "Safety runbook readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_safety_runbook_readiness_route() -> SafetyRunbookReadinessResponse:
    return build_safety_runbook_readiness()


@router.get(
    "/governance-status",
    response_model=SafetyGovernanceStatusResponse,
    operation_id="getSafetyGovernanceStatus",
    summary="Get lotus-ai safety governance status",
    description=(
        "Returns the current governance posture for safety runtime enforcement, including runtime, runbook, and evidence readiness."
    ),
    responses={
        200: {"description": "Safety governance status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_safety_governance_status_route() -> SafetyGovernanceStatusResponse:
    return build_safety_governance_status()
