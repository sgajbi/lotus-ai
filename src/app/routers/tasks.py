from __future__ import annotations

from fastapi import APIRouter

from app.contracts.tasks import TaskExecutionRequest, TaskExecutionResponse
from app.services.task_executor import execute_task

router = APIRouter(prefix="/ai/tasks", tags=["tasks"])


@router.post(
    "/execute",
    response_model=TaskExecutionResponse,
    operation_id="executeTask",
    summary="Execute a bounded lotus-ai task",
    description=(
        "Validates and executes a bounded lotus-ai task using the current delivery-phase "
        "execution policy. During foundation phase, supported tasks return deterministic "
        "stub responses so downstream Lotus apps can integrate against stable contracts "
        "before live provider execution is enabled."
    ),
    responses={
        200: {"description": "Task executed successfully."},
        403: {"description": "Caller is not authorized for the protected task execution path."},
        404: {"description": "Unknown task id."},
        409: {"description": "Task disabled or request conflicts with task policy."},
        500: {"description": "Unexpected server error."},
    },
)
async def execute_task_route(request: TaskExecutionRequest) -> TaskExecutionResponse:
    return execute_task(request)
