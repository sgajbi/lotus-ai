from __future__ import annotations

from app.contracts.workflow_packs import WorkflowPackRuntimeStatusSummaryResponse
from app.services.workflow_pack_bindings import list_workflow_pack_execution_binding_descriptors
from app.services.workflow_pack_registry import list_workflow_pack_registrations


def build_workflow_pack_runtime_status_summary() -> WorkflowPackRuntimeStatusSummaryResponse:
    registrations = list_workflow_pack_registrations()
    execution_bindings = list_workflow_pack_execution_binding_descriptors()
    binding_refs = {f"{binding.pack_id}@{binding.version}" for binding in execution_bindings}
    registered_registrations = [
        registration
        for registration in registrations
        if registration.registration_status.value == "REGISTERED"
    ]
    registered_registration_refs = [
        f"{registration.pack_id}@{registration.version}" for registration in registered_registrations
    ]
    executable_registrations = [
        registration
        for registration in registered_registrations
        if f"{registration.pack_id}@{registration.version}" in binding_refs
    ]
    executable_registration_refs = sorted(
        f"{registration.pack_id}@{registration.version}" for registration in executable_registrations
    )
    executable_review_required_refs = sorted(
        f"{registration.pack_id}@{registration.version}"
        for registration in executable_registrations
        if registration.default_execution_mode.value == "REVIEW_GATED"
    )
    registered_count = len(registered_registration_refs)
    executable_registration_count = len(executable_registration_refs)
    executable_review_required_count = len(executable_review_required_refs)
    registered_without_execution_binding_count = registered_count - executable_registration_count

    return WorkflowPackRuntimeStatusSummaryResponse(
        registration_count=len(registrations),
        registered_count=registered_count,
        execution_binding_count=len(execution_bindings),
        executable_registration_count=executable_registration_count,
        executable_review_required_count=executable_review_required_count,
        executable_without_review_count=(
            executable_registration_count - executable_review_required_count
        ),
        registered_without_execution_binding_count=registered_without_execution_binding_count,
        executable_registration_refs=executable_registration_refs,
        executable_review_required_refs=executable_review_required_refs,
        status_summary=[
            "Workflow-pack runtime readiness is narrower than catalog presence and counts only versions that are both REGISTERED and explicitly bound for lotus-ai execution.",
            "Executable workflow-pack versions are further split by whether the registered default execution mode still requires human review before downstream use.",
            "Registered workflow-pack versions without an explicit execution binding remain visible as governed catalog entries but are not yet executable through the current bounded lotus-ai runtime path.",
            "Use the workflow-pack registry detail surface for owner-artifact truth and the platform runtime status summary for estate-level execution readiness posture.",
        ],
    )
