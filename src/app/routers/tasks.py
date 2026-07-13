from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.contracts.tasks import TaskExecutionRequest, TaskExecutionResponse
from app.http.authenticated_caller import AuthenticatedCallerDependency
from app.services.task_executor import execute_task
from app.services.workflow_pack_run_ledger import WorkflowPackRunStoreUnavailableError
from app.services.workflow_pack_task_flow_service import WorkflowPackTaskFlowStoreNotReadyError

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
        503: {
            "description": (
                "Workflow-pack runtime store is not ready for this pack-backed task path."
            )
        },
        500: {"description": "Unexpected server error."},
    },
)
async def execute_task_route(
    request: TaskExecutionRequest,
    _authenticated_caller: AuthenticatedCallerDependency,
) -> TaskExecutionResponse:
    try:
        return execute_task(request)
    except WorkflowPackRunStoreUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except WorkflowPackTaskFlowStoreNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
