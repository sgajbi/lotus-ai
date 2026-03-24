from __future__ import annotations

from fastapi import APIRouter

from app.contracts.access_control import (
    AccessControlGovernanceStatusResponse,
    AccessControlRuntimeStatusResponse,
    CallerPolicyCatalogResponse,
)
from app.services.access_control_governance import build_access_control_governance_status
from app.services.access_control_runtime import (
    build_access_control_runtime_status,
    list_caller_policies,
)

router = APIRouter(prefix="/platform/access-control", tags=["platform"])


@router.get(
    "/runtime-status",
    response_model=AccessControlRuntimeStatusResponse,
    operation_id="getAccessControlRuntimeStatus",
    summary="Get access-control runtime status",
    description=(
        "Returns the current caller-registry and access-control runtime posture, including store "
        "readiness and whether authorization remains documentary or is ready for broader enforcement."
    ),
    responses={
        200: {"description": "Access-control runtime status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_access_control_runtime_status_route() -> AccessControlRuntimeStatusResponse:
    return build_access_control_runtime_status()


@router.get(
    "/governance-status",
    response_model=AccessControlGovernanceStatusResponse,
    operation_id="getAccessControlGovernanceStatus",
    summary="Get access-control governance status",
    description=(
        "Returns the current governance posture for caller identity and tenant isolation, including "
        "whether the registry is durable enough for stronger enforcement."
    ),
    responses={
        200: {"description": "Access-control governance status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_access_control_governance_status_route() -> AccessControlGovernanceStatusResponse:
    return build_access_control_governance_status()


@router.get(
    "/caller-policies",
    response_model=CallerPolicyCatalogResponse,
    operation_id="listCallerPolicies",
    summary="List caller access-control policies",
    description=(
        "Returns the bounded caller policy registry currently recognized by lotus-ai, including "
        "task, retrieval, live-provider, and control-plane capability posture."
    ),
    responses={
        200: {"description": "Caller policy catalog returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def list_caller_policies_route() -> CallerPolicyCatalogResponse:
    return list_caller_policies()
