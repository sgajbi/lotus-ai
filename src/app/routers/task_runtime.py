from __future__ import annotations

from fastapi import APIRouter, Query

from app.contracts.task_runtime import TaskExecutionSummaryResponse, TaskRuntimeStatusResponse
from app.services.task_execution_summary import build_task_execution_summary
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


@router.get(
    "/execution-summary",
    response_model=TaskExecutionSummaryResponse,
    operation_id="getTaskExecutionSummary",
    summary="Get lotus-ai task execution summary",
    description=(
        "Returns a bounded sampled summary of persisted task executions grouped by task category "
        "and provider mode."
    ),
    responses={
        200: {"description": "Task execution summary returned successfully."},
        422: {"description": "Invalid query parameters supplied."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_task_execution_summary_route(
    limit: int = Query(
        default=100,
        ge=1,
        le=200,
        description="Maximum number of recent audit records to sample for the summary.",
    ),
) -> TaskExecutionSummaryResponse:
    return build_task_execution_summary(limit=limit)
