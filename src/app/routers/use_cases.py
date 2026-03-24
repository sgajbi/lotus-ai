from __future__ import annotations

from fastapi import APIRouter

from app.contracts.use_cases import FirstUseCaseRuntimeStatusResponse
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
