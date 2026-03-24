from __future__ import annotations

from fastapi import APIRouter

from app.contracts.use_cases import FirstUseCaseReadinessResponse, FirstUseCaseRuntimeStatusResponse
from app.services.first_use_case_readiness import build_first_use_case_readiness
from app.services.first_use_case_status import build_first_use_case_runtime_status

router = APIRouter(prefix="/platform/use-cases", tags=["platform"])


@router.get(
    "/first-production-use-case",
    response_model=FirstUseCaseRuntimeStatusResponse,
    operation_id="getFirstProductionUseCaseStatus",
    summary="Get lotus-ai first production use-case contract status",
    description=(
        "Returns the currently selected first production-oriented downstream use case, including "
        "the bounded contract fields and ownership boundaries defined for onboarding."
    ),
    responses={
        200: {"description": "First production use-case status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_first_production_use_case_status_route() -> FirstUseCaseRuntimeStatusResponse:
    return build_first_use_case_runtime_status()


@router.get(
    "/first-production-use-case/readiness",
    response_model=FirstUseCaseReadinessResponse,
    operation_id="getFirstProductionUseCaseReadiness",
    summary="Get lotus-ai first production use-case readiness status",
    description=(
        "Returns the bounded readiness posture for the selected first production-oriented use "
        "case, including caller identity, safety posture, and runtime-backed evaluation evidence."
    ),
    responses={
        200: {"description": "First production use-case readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_first_production_use_case_readiness_route() -> FirstUseCaseReadinessResponse:
    return build_first_use_case_readiness()
