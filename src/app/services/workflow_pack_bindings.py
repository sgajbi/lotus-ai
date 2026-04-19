from __future__ import annotations

from dataclasses import dataclass

from app.contracts.workflow_packs import WorkflowPackRegistrationDescriptor
from app.services.task_execution_models import TaskExecutionContext
from app.services.workflow_pack_registry import get_workflow_pack_registration


@dataclass(frozen=True)
class WorkflowPackExecutionBinding:
    pack_id: str
    version: str
    task_id: str
    required_payload_keys: frozenset[str]
    default_workflow_surface: str

    def supports_task_execution_context(
        self,
        *,
        context: TaskExecutionContext,
        registration: WorkflowPackRegistrationDescriptor,
    ) -> bool:
        return (
            context.capability.task_id == self.task_id
            and context.request.caller.caller_app in registration.supported_callers
            and self.validate_task_request_payload(payload=context.request.context.payload)
            and self.supports_registration_scope(registration=registration)
        )

    def validate_task_request_payload(self, *, payload: dict[str, object]) -> bool:
        return self.required_payload_keys.issubset(payload.keys())

    def supports_registration_scope(
        self, *, registration: WorkflowPackRegistrationDescriptor
    ) -> bool:
        return not registration.surface_scope or self.default_workflow_surface in set(
            registration.surface_scope
        )


_WORKFLOW_PACK_EXECUTION_BINDINGS = (
    WorkflowPackExecutionBinding(
        pack_id="advisor_brief.pack",
        version="v1",
        task_id="explain.v1",
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
            if (
                (registration := get_workflow_pack_registration(
                    pack_id=binding.pack_id,
                    version=binding.version,
                ))
                is not None
                and binding.supports_task_execution_context(
                    context=context,
                    registration=registration,
                )
            )
        ),
        None,
    )


def validate_workflow_pack_execution_bindings() -> None:
    for binding in _WORKFLOW_PACK_EXECUTION_BINDINGS:
        registration = get_workflow_pack_registration(
            pack_id=binding.pack_id,
            version=binding.version,
        )
        if registration is None:
            raise ValueError(
                f"Workflow-pack execution binding missing registration: {binding.pack_id}@{binding.version}"
            )
        if not binding.supports_registration_scope(registration=registration):
            raise ValueError(
                "Workflow-pack execution binding default surface is outside registration scope: "
                f"{binding.pack_id}@{binding.version}"
            )
