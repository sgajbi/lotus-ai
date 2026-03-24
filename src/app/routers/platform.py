from __future__ import annotations

from fastapi import APIRouter, Request

from app.contracts.platform import PlatformRuntimeStatusResponse
from app.contracts.production_baseline import ProductionBaselineRuntimeStatusResponse
from app.services.platform_status import build_platform_runtime_status
from app.services.production_baseline_runtime import build_production_baseline_runtime_status

router = APIRouter(prefix="/platform", tags=["platform"])


@router.get(
    "/runtime-status",
    response_model=PlatformRuntimeStatusResponse,
    operation_id="getPlatformRuntimeStatus",
    summary="Get lotus-ai platform runtime status",
    description=(
        "Returns the current lotus-ai operating posture across provider execution, safety, "
        "prompt registry, retrieval, and persistence modes."
    ),
    responses={
        200: {"description": "Platform runtime status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_platform_runtime_status_route(request: Request) -> PlatformRuntimeStatusResponse:
    return build_platform_runtime_status(request.app.state)


@router.get(
    "/production-baseline/runtime-status",
    response_model=ProductionBaselineRuntimeStatusResponse,
    operation_id="getProductionBaselineRuntimeStatus",
    summary="Get RFC-0020 production-baseline runtime status",
    description=(
        "Returns the current lotus-ai production-baseline posture across the major dependencies "
        "needed to distinguish local or demo-capable runtime, prod-shaped local runtime, and "
        "production-ready runtime."
    ),
    responses={
        200: {"description": "Production-baseline runtime status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_production_baseline_runtime_status_route(
    request: Request,
) -> ProductionBaselineRuntimeStatusResponse:
    return build_production_baseline_runtime_status(request.app.state)
