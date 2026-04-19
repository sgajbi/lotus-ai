from __future__ import annotations

from app.config import settings
from app.contracts.workflow_packs import (
    WorkflowPackControlEventDescriptor,
    WorkflowPackRegistrationDescriptor,
    WorkflowPackRegistrationDetailResponse,
    WorkflowPackRegistryCatalogResponse,
)
from app.services.workflow_pack_registry_seed import (
    build_workflow_pack_validation_rules,
    validate_workflow_pack_registrations,
)
from app.services.workflow_pack_registry_store import (
    get_workflow_pack_registry_store,
    reset_workflow_pack_registry_store_cache,
)


def build_workflow_pack_registry_catalog() -> WorkflowPackRegistryCatalogResponse:
    registrations = _validated_registrations()
    registered_count = sum(
        1
        for registration in registrations
        if registration.registration_status.value == "REGISTERED"
    )
    production_eligible_count = sum(
        1
        for registration in registrations
        if "PRODUCTION" in [environment.value for environment in registration.supported_environments]
    )
    return WorkflowPackRegistryCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        phase=settings.delivery_phase,
        registration_count=len(registrations),
        registered_count=registered_count,
        production_eligible_count=production_eligible_count,
        registrations=registrations,
        validation_rules=build_workflow_pack_validation_rules(),
        status_summary=[
            "Workflow-pack registry records are modeled separately from capability-pack maturity so runtime activation can stay explicit and auditable.",
            "Seed-owned workflow-pack definitions remain code-grounded while mutable activation state and control history now flow through the configured registry store.",
            "Only declared workflow-pack versions with valid ownership, scope, and definition references are eligible to advance into activation evaluation.",
        ],
    )


def build_workflow_pack_registration_detail(
    pack_id: str,
    version: str,
) -> WorkflowPackRegistrationDetailResponse:
    registration = get_workflow_pack_registration(pack_id=pack_id, version=version)
    if registration is None:
        raise ValueError(f"Unknown workflow-pack registration: {pack_id}@{version}")

    return WorkflowPackRegistrationDetailResponse(
        service=settings.service_name,
        version=settings.service_version,
        registration=registration,
        validation_rules=build_workflow_pack_validation_rules(),
        denied_without_registration=True,
        status_summary=[
            "Workflow-pack execution remains deny-by-default for versions that do not resolve through the governed registry.",
            "This record captures activation posture and ownership metadata without duplicating business workflow logic from the owning repository.",
        ],
    )


def get_workflow_pack_registration(
    *, pack_id: str, version: str
) -> WorkflowPackRegistrationDescriptor | None:
    return get_workflow_pack_registry_store().get_registration(pack_id=pack_id, version=version)


def save_workflow_pack_registration(registration: WorkflowPackRegistrationDescriptor) -> None:
    registrations = _validated_registrations()
    updated_registrations: list[WorkflowPackRegistrationDescriptor] = []
    replaced = False
    for existing in registrations:
        if existing.pack_id == registration.pack_id and existing.version == registration.version:
            updated_registrations.append(registration)
            replaced = True
            continue
        updated_registrations.append(existing)
    if not replaced:
        updated_registrations.append(registration)
    validate_workflow_pack_registrations(updated_registrations)
    get_workflow_pack_registry_store().save_registration(registration)


def list_workflow_pack_control_events(
    *,
    pack_id: str | None = None,
    version: str | None = None,
    limit: int = 20,
) -> list[WorkflowPackControlEventDescriptor]:
    return get_workflow_pack_registry_store().list_control_events(
        pack_id=pack_id,
        version=version,
        limit=limit,
    )


def append_workflow_pack_control_event(event: WorkflowPackControlEventDescriptor) -> None:
    get_workflow_pack_registry_store().save_control_event(event)


def reset_workflow_pack_registry_state() -> None:
    reset_workflow_pack_registry_store_cache()


def _validated_registrations() -> list[WorkflowPackRegistrationDescriptor]:
    registrations = get_workflow_pack_registry_store().list_registrations()
    validate_workflow_pack_registrations(registrations)
    return registrations
