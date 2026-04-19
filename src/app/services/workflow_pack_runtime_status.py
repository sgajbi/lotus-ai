from __future__ import annotations

from app.contracts.workflow_packs import WorkflowPackRuntimeStatusSummaryResponse
from app.services.workflow_pack_bindings import list_workflow_pack_execution_binding_descriptors
from app.services.workflow_pack_registry import list_workflow_pack_registrations


def build_workflow_pack_runtime_status_summary() -> WorkflowPackRuntimeStatusSummaryResponse:
    registrations = list_workflow_pack_registrations()
    execution_bindings = list_workflow_pack_execution_binding_descriptors()
    binding_refs = {f"{binding.pack_id}@{binding.version}" for binding in execution_bindings}
    registered_registration_refs = [
        f"{registration.pack_id}@{registration.version}"
        for registration in registrations
        if registration.registration_status.value == "REGISTERED"
    ]
    executable_registration_refs = sorted(
        registration_ref
        for registration_ref in registered_registration_refs
        if registration_ref in binding_refs
    )
    registered_count = len(registered_registration_refs)
    executable_registration_count = len(executable_registration_refs)
    registered_without_execution_binding_count = registered_count - executable_registration_count

    return WorkflowPackRuntimeStatusSummaryResponse(
        registration_count=len(registrations),
        registered_count=registered_count,
        execution_binding_count=len(execution_bindings),
        executable_registration_count=executable_registration_count,
        registered_without_execution_binding_count=registered_without_execution_binding_count,
        executable_registration_refs=executable_registration_refs,
        status_summary=[
            "Workflow-pack runtime readiness is narrower than catalog presence and counts only versions that are both REGISTERED and explicitly bound for lotus-ai execution.",
            "Registered workflow-pack versions without an explicit execution binding remain visible as governed catalog entries but are not yet executable through the current bounded lotus-ai runtime path.",
            "Use the workflow-pack registry detail surface for owner-artifact truth and the platform runtime status summary for estate-level execution readiness posture.",
        ],
    )
