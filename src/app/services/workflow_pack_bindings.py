from __future__ import annotations

from dataclasses import dataclass

from app.services.task_execution_models import TaskExecutionContext


@dataclass(frozen=True)
class WorkflowPackExecutionBinding:
    pack_id: str
    version: str
    task_id: str
    allowed_callers: frozenset[str]
    required_payload_keys: frozenset[str]
    default_workflow_surface: str

    def supports_task_execution_context(self, *, context: TaskExecutionContext) -> bool:
        return (
            context.capability.task_id == self.task_id
            and context.request.caller.caller_app in self.allowed_callers
            and self.required_payload_keys.issubset(context.request.context.payload.keys())
        )

    def validate_task_request_payload(self, *, payload: dict[str, object]) -> bool:
        return self.required_payload_keys.issubset(payload.keys())


_WORKFLOW_PACK_EXECUTION_BINDINGS = (
    WorkflowPackExecutionBinding(
        pack_id="advisor_brief.pack",
        version="v1",
        task_id="explain.v1",
        allowed_callers=frozenset({"lotus-gateway"}),
        required_payload_keys=frozenset({"portfolio", "period", "performance", "supportability"}),
        default_workflow_surface="advisor-brief-workspace",
    ),
)


def get_workflow_pack_execution_binding(
    *,
    pack_id: str,
    version: str,
) -> WorkflowPackExecutionBinding | None:
    return next(
        (
            binding
            for binding in _WORKFLOW_PACK_EXECUTION_BINDINGS
            if binding.pack_id == pack_id and binding.version == version
        ),
        None,
    )


def resolve_workflow_pack_execution_binding_for_task(
    *,
    context: TaskExecutionContext,
) -> WorkflowPackExecutionBinding | None:
    return next(
        (
            binding
            for binding in _WORKFLOW_PACK_EXECUTION_BINDINGS
            if binding.supports_task_execution_context(context=context)
        ),
        None,
    )
