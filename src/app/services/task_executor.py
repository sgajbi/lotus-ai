from __future__ import annotations

from app.contracts.tasks import TaskExecutionRequest, TaskExecutionResponse
from app.contracts.workflow_pack_runs import WorkflowPackRunDescriptor
from app.services.task_execution_pipeline import (
    build_task_execution_response,
    persist_task_execution_audit,
    resolve_task_execution,
    validate_task_request,
)
from app.services.workflow_pack_run_ledger import record_workflow_pack_run_for_task_execution


def execute_task(request: TaskExecutionRequest) -> TaskExecutionResponse:
    response, _ = execute_task_with_optional_workflow_pack_recording(request)
    return response


def execute_task_with_optional_workflow_pack_recording(
    request: TaskExecutionRequest,
) -> tuple[TaskExecutionResponse, WorkflowPackRunDescriptor | None]:
    context = validate_task_request(request)
    resolved = resolve_task_execution(context=context)
    response = build_task_execution_response(resolved=resolved)
    persist_task_execution_audit(context=context, response=response)
    workflow_pack_run = record_workflow_pack_run_for_task_execution(context=context, response=response)
    return _attach_workflow_pack_run_id(response=response, workflow_pack_run=workflow_pack_run), workflow_pack_run


def _attach_workflow_pack_run_id(
    *,
    response: TaskExecutionResponse,
    workflow_pack_run: WorkflowPackRunDescriptor | None,
) -> TaskExecutionResponse:
    if workflow_pack_run is None:
        return response
    return response.model_copy(
        update={
            "audit": response.audit.model_copy(
                update={"workflow_pack_run_id": workflow_pack_run.run_id}
            )
        }
    )
