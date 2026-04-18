from __future__ import annotations

from app.contracts.tasks import TaskExecutionRequest, TaskExecutionResponse
from app.services.task_execution_pipeline import (
    build_task_execution_response,
    persist_task_execution_audit,
    resolve_task_execution,
    validate_task_request,
)
from app.services.workflow_pack_run_ledger import record_workflow_pack_run_for_task_execution


def execute_task(request: TaskExecutionRequest) -> TaskExecutionResponse:
    context = validate_task_request(request)
    resolved = resolve_task_execution(context=context)
    response = build_task_execution_response(resolved=resolved)
    persist_task_execution_audit(context=context, response=response)
    record_workflow_pack_run_for_task_execution(context=context, response=response)
    return response
