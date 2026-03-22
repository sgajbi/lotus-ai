from __future__ import annotations

from app.contracts.tasks import TaskExecutionRequest, TaskExecutionResponse
from app.services.task_execution_pipeline import (
    build_task_execution_response,
    persist_task_execution_audit,
    resolve_task_execution,
    validate_task_request,
)


def execute_task(request: TaskExecutionRequest) -> TaskExecutionResponse:
    capability = validate_task_request(request)
    resolved = resolve_task_execution(request, capability=capability)
    response = build_task_execution_response(request, resolved=resolved)
    persist_task_execution_audit(request, response=response)
    return response
