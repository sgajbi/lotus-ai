from __future__ import annotations

from fastapi import APIRouter

from app.contracts.async_runtime import AsyncRuntimeStatusResponse
from app.services.async_runtime_status import build_async_runtime_status

router = APIRouter(prefix="/platform/async", tags=["platform"])


@router.get(
    "/runtime-status",
    response_model=AsyncRuntimeStatusResponse,
    operation_id="getAsyncRuntimeStatus",
    summary="Get lotus-ai async runtime status",
    description=(
        "Returns the current queue and worker posture for lotus-ai async execution, including "
        "known async job types and whether live background execution is active."
    ),
    responses={
        200: {"description": "Async runtime status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_async_runtime_status_route() -> AsyncRuntimeStatusResponse:
    return build_async_runtime_status()
