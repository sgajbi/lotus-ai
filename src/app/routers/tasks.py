from __future__ import annotations

from fastapi import APIRouter

from app.contracts.tasks import TaskExecutionRequest, TaskExecutionResponse
from app.services.task_executor import execute_task

router = APIRouter(prefix="/ai/tasks", tags=["tasks"])


@router.post(
    "/execute",
    response_model=TaskExecutionResponse,
    summary="Execute a bounded lotus-ai task",
    description=(
        "Validates and executes a bounded lotus-ai task using the current delivery-phase "
        "execution policy. During foundation phase, supported tasks return deterministic "
        "stub responses so downstream Lotus apps can integrate against stable contracts "
        "before live provider execution is enabled."
    ),
)
async def execute_task_route(request: TaskExecutionRequest) -> TaskExecutionResponse:
    return execute_task(request)
