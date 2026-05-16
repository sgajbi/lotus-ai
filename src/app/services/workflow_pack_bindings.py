from __future__ import annotations

from dataclasses import dataclass

from app.contracts.workflow_packs import (
    WorkflowPackExecutionBindingDescriptor,
    WorkflowPackRegistrationDescriptor,
)
from app.services.workflow_pack_phase1_specs import (
    ADVISOR_BRIEF_V1_SPEC,
    DPM_EXCEPTION_SUMMARY_V1_SPEC,
    DPM_OPERATIONS_HANDOFF_SUMMARY_V1_SPEC,
    DPM_WAVE_PM_MEMO_V1_SPEC,
    OUTCOME_REVIEW_NARRATIVE_V1_SPEC,
    PM_QUALITY_SUMMARY_V1_SPEC,
    PROOF_PACK_PM_MEMO_V1_SPEC,
    TWR_INSPECTION_SUPPORT_BRIEF_V1_SPEC,
    WORKSPACE_RATIONALE_V1_SPEC,
    WorkflowPackPhase1VersionSpec,
)
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


@dataclass(frozen=True)
class ResolvedWorkflowPackExecutionBinding:
    binding: WorkflowPackExecutionBinding
    registration: WorkflowPackRegistrationDescriptor


def _build_execution_binding_from_spec(
    spec: WorkflowPackPhase1VersionSpec,
) -> WorkflowPackExecutionBinding:
    if spec.execution_task_id is None:
        raise ValueError("Phase-1 execution binding spec missing execution_task_id.")
    if spec.default_workflow_surface is None:
        raise ValueError("Phase-1 execution binding spec missing default_workflow_surface.")
    return WorkflowPackExecutionBinding(
        pack_id=spec.pack_id,
        version=spec.version,
        task_id=spec.execution_task_id,
        required_payload_keys=spec.required_payload_keys,
        default_workflow_surface=spec.default_workflow_surface,
    )


_WORKFLOW_PACK_EXECUTION_BINDINGS = (
    _build_execution_binding_from_spec(ADVISOR_BRIEF_V1_SPEC),
    _build_execution_binding_from_spec(WORKSPACE_RATIONALE_V1_SPEC),
    _build_execution_binding_from_spec(TWR_INSPECTION_SUPPORT_BRIEF_V1_SPEC),
    _build_execution_binding_from_spec(PROOF_PACK_PM_MEMO_V1_SPEC),
    _build_execution_binding_from_spec(OUTCOME_REVIEW_NARRATIVE_V1_SPEC),
    _build_execution_binding_from_spec(DPM_WAVE_PM_MEMO_V1_SPEC),
    _build_execution_binding_from_spec(DPM_OPERATIONS_HANDOFF_SUMMARY_V1_SPEC),
    _build_execution_binding_from_spec(DPM_EXCEPTION_SUMMARY_V1_SPEC),
    _build_execution_binding_from_spec(PM_QUALITY_SUMMARY_V1_SPEC),
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


def get_resolved_workflow_pack_execution_binding(
    *,
    pack_id: str,
    version: str,
) -> ResolvedWorkflowPackExecutionBinding | None:
    binding = get_workflow_pack_execution_binding(pack_id=pack_id, version=version)
    if binding is None:
        return None
    registration = get_workflow_pack_registration(pack_id=pack_id, version=version)
    if registration is None:
        return None
    return ResolvedWorkflowPackExecutionBinding(binding=binding, registration=registration)


def resolve_workflow_pack_execution_binding_for_task(
    *,
    context: TaskExecutionContext,
) -> ResolvedWorkflowPackExecutionBinding | None:
    return next(
        (
            resolved_binding
            for binding in _WORKFLOW_PACK_EXECUTION_BINDINGS
            if (
                (
                    resolved_binding := get_resolved_workflow_pack_execution_binding(
                        pack_id=binding.pack_id,
                        version=binding.version,
                    )
                )
                is not None
                and binding.supports_task_execution_context(
                    context=context,
                    registration=resolved_binding.registration,
                )
            )
        ),
        None,
    )


def validate_workflow_pack_execution_bindings() -> None:
    for binding in _WORKFLOW_PACK_EXECUTION_BINDINGS:
        resolved_binding = get_resolved_workflow_pack_execution_binding(
            pack_id=binding.pack_id,
            version=binding.version,
        )
        if resolved_binding is None:
            raise ValueError(
                f"Workflow-pack execution binding missing registration: {binding.pack_id}@{binding.version}"
            )
        if not binding.supports_registration_scope(registration=resolved_binding.registration):
            raise ValueError(
                "Workflow-pack execution binding default surface is outside registration scope: "
                f"{binding.pack_id}@{binding.version}"
            )


def list_workflow_pack_execution_binding_descriptors() -> list[
    WorkflowPackExecutionBindingDescriptor
]:
    return [
        _map_workflow_pack_execution_binding_descriptor(binding)
        for binding in _WORKFLOW_PACK_EXECUTION_BINDINGS
    ]


def get_workflow_pack_execution_binding_descriptor(
    *,
    pack_id: str,
    version: str,
) -> WorkflowPackExecutionBindingDescriptor | None:
    binding = get_workflow_pack_execution_binding(pack_id=pack_id, version=version)
    if binding is None:
        return None
    return _map_workflow_pack_execution_binding_descriptor(binding)


def _map_workflow_pack_execution_binding_descriptor(
    binding: WorkflowPackExecutionBinding,
) -> WorkflowPackExecutionBindingDescriptor:
    return WorkflowPackExecutionBindingDescriptor(
        pack_id=binding.pack_id,
        version=binding.version,
        task_id=binding.task_id,
        default_workflow_surface=binding.default_workflow_surface,
        required_payload_keys=sorted(binding.required_payload_keys),
    )
