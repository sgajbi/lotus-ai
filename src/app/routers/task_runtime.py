from __future__ import annotations

from fastapi import APIRouter

from app.contracts.task_runtime import TaskRuntimeStatusResponse
from app.services.task_runtime_status import build_task_runtime_status

router = APIRouter(prefix="/platform/tasks", tags=["platform"])


@router.get(
    "/runtime-status",
    response_model=TaskRuntimeStatusResponse,
    operation_id="getTaskRuntimeStatus",
    summary="Get lotus-ai task runtime status",
    description=(
        "Returns the current bounded task-runtime posture across stub-backed and retrieval-backed "
        "task execution paths."
    ),
    responses={
        200: {"description": "Task runtime status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_task_runtime_status_route() -> TaskRuntimeStatusResponse:
    return build_task_runtime_status()
