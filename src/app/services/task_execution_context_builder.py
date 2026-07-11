from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.contracts.tasks import TaskExecutionRequest
from app.contracts.tasks import TaskCategory
from app.contracts.access_control import AuthorizationCapabilityType
from app.services.access_control_authorization import authorize_request, require_authorized
from app.services.knowledge_retrieval_request import extract_knowledge_source_ids
from app.services.prompt_runtime import (
    build_prompt_selection_trace,
    resolve_runtime_prompt_or_raise,
)
from app.services.safety_runtime import build_safety_execution_outcome
from app.services.task_capability_validator import validate_task_capability
from app.services.task_execution_models import TaskExecutionContext


def build_task_execution_context(request: TaskExecutionRequest) -> TaskExecutionContext:
    capability = validate_task_capability(request)
    requested_source_ids = (
        extract_knowledge_source_ids(payload=request.context.payload, task_id=capability.task_id)
        if capability.category in {TaskCategory.KNOWLEDGE_SEARCH, TaskCategory.KNOWLEDGE_ANSWER}
        else []
    )
    authorization = require_authorized(
        authorize_request(
            caller_app=request.caller.caller_app,
            capability_type=AuthorizationCapabilityType.TASK_EXECUTION,
            tenant_id=request.caller.tenant_id,
            task_id=capability.task_id,
            source_ids=requested_source_ids,
        )
    )
    resolved_prompt = resolve_runtime_prompt_or_raise(request.task_id)
    safety_outcome = build_safety_execution_outcome(capability.output_label)
    return TaskExecutionContext(
        request=request,
        capability=capability,
        authorization=authorization,
        prompt=resolved_prompt.prompt,
        prompt_selection=build_prompt_selection_trace(request.task_id),
        safety_outcome=safety_outcome,
        request_id=f"air_{uuid4().hex}",
        execution_started_at=datetime.now(UTC).isoformat(),
    )
