from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.contracts.tasks import TaskExecutionRequest
from app.services.prompt_runtime import (
    build_prompt_selection_trace,
    resolve_runtime_prompt_or_raise,
)
from app.services.safety_runtime import build_safety_execution_outcome
from app.services.task_capability_validator import validate_task_capability
from app.services.task_execution_models import TaskExecutionContext


def build_task_execution_context(request: TaskExecutionRequest) -> TaskExecutionContext:
    capability = validate_task_capability(request)
    resolved_prompt = resolve_runtime_prompt_or_raise(request.task_id)
    safety_outcome = build_safety_execution_outcome(capability.output_label)
    return TaskExecutionContext(
        request=request,
        capability=capability,
        prompt=resolved_prompt.prompt,
        prompt_selection=build_prompt_selection_trace(request.task_id),
        safety_outcome=safety_outcome,
        request_id=f"air_{uuid4().hex}",
        generated_at=datetime.now(UTC).isoformat(),
    )
