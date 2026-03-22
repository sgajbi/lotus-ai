from __future__ import annotations

from fastapi import APIRouter

from app.contracts.platform import PlatformRuntimeStatusResponse
from app.services.platform_status import build_platform_runtime_status

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
async def get_platform_runtime_status_route() -> PlatformRuntimeStatusResponse:
    return build_platform_runtime_status()
