from __future__ import annotations

from app.config import settings
from app.contracts.runtime_readiness import RuntimeReadinessStatus
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
from app.services.runtime_readiness import get_workflow_pack_registry_store_runtime_status


class WorkflowPackRegistryUnavailableError(RuntimeError):
    pass


def build_workflow_pack_registry_catalog() -> WorkflowPackRegistryCatalogResponse:
    from app.services.workflow_pack_bindings import (
        list_workflow_pack_execution_binding_descriptors,
    )
    from app.services.workflow_pack_queue_policy_catalog import (
        list_workflow_pack_queue_policy_descriptors,
    )

    registrations = list_workflow_pack_registrations()
    registered_count = sum(
        1
        for registration in registrations
        if registration.registration_status.value == "REGISTERED"
    )
    production_eligible_count = sum(
        1
        for registration in registrations
        if "PRODUCTION"
        in [environment.value for environment in registration.supported_environments]
    )
    return WorkflowPackRegistryCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        phase=settings.delivery_phase,
        registration_count=len(registrations),
        registered_count=registered_count,
        production_eligible_count=production_eligible_count,
        registrations=registrations,
        execution_bindings=list_workflow_pack_execution_binding_descriptors(),
        queue_policies=list_workflow_pack_queue_policy_descriptors(),
        validation_rules=build_workflow_pack_validation_rules(),
        status_summary=[
            "Workflow-pack registry records are modeled separately from capability-pack maturity so runtime activation can stay explicit and auditable.",
            "Seed-owned workflow-pack definitions remain code-grounded while mutable activation state and control history now flow through the configured registry store.",
            "Only declared workflow-pack versions with valid ownership, scope, and definition references are eligible to advance into activation evaluation.",
            "Internal execution bindings are validated against the same registry scope so task-shape hints cannot silently drift away from caller or surface truth.",
            "Registry inspection now shows which registered workflow-pack versions also have an explicit lotus-ai execution binding, including task and default surface posture.",
            "Queue-policy inspection is version-scoped and declarative; runtime queue admission is intentionally separate from registry posture.",
        ],
    )


def build_workflow_pack_registration_detail(
    pack_id: str,
    version: str,
) -> WorkflowPackRegistrationDetailResponse:
    from app.services.workflow_pack_bindings import (
        get_workflow_pack_execution_binding_descriptor,
    )
    from app.services.workflow_pack_queue_policy_catalog import (
        get_workflow_pack_queue_policy_descriptor,
        validate_workflow_pack_queue_policies,
    )

    registration = get_workflow_pack_registration(pack_id=pack_id, version=version)
    if registration is None:
        raise ValueError(f"Unknown workflow-pack registration: {pack_id}@{version}")
    validate_workflow_pack_queue_policies()

    return WorkflowPackRegistrationDetailResponse(
        service=settings.service_name,
        version=settings.service_version,
        registration=registration,
        execution_binding=get_workflow_pack_execution_binding_descriptor(
            pack_id=pack_id,
            version=version,
        ),
        queue_policy=get_workflow_pack_queue_policy_descriptor(
            pack_id=pack_id,
            version=version,
        ),
        validation_rules=build_workflow_pack_validation_rules(),
        denied_without_registration=True,
        status_summary=[
            "Workflow-pack execution remains deny-by-default for versions that do not resolve through the governed registry.",
            "This record captures activation posture and ownership metadata without duplicating business workflow logic from the owning repository.",
            "When an explicit execution binding exists, this detail view also shows the current task and default workflow-surface mapping implemented by lotus-ai.",
            "When an explicit queue policy exists, it remains declarative scheduling policy and does not imply runtime admission has already executed.",
        ],
    )


def get_workflow_pack_registration(
    *, pack_id: str, version: str
) -> WorkflowPackRegistrationDescriptor | None:
    _require_workflow_pack_registry_ready()
    return get_workflow_pack_registry_store().get_registration(pack_id=pack_id, version=version)


def list_workflow_pack_registrations() -> list[WorkflowPackRegistrationDescriptor]:
    _require_workflow_pack_registry_ready()
    return _validated_registrations()


def save_workflow_pack_registration(registration: WorkflowPackRegistrationDescriptor) -> None:
    _require_workflow_pack_registry_ready()
    registrations = list_workflow_pack_registrations()
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
    _require_workflow_pack_registry_ready()
    return get_workflow_pack_registry_store().list_control_events(
        pack_id=pack_id,
        version=version,
        limit=limit,
    )


def append_workflow_pack_control_event(event: WorkflowPackControlEventDescriptor) -> None:
    _require_workflow_pack_registry_ready()
    get_workflow_pack_registry_store().save_control_event(event)


def reset_workflow_pack_registry_state() -> None:
    reset_workflow_pack_registry_store_cache()


def _validated_registrations() -> list[WorkflowPackRegistrationDescriptor]:
    from app.services.workflow_pack_bindings import validate_workflow_pack_execution_bindings
    from app.services.workflow_pack_queue_policy_catalog import (
        validate_workflow_pack_queue_policies,
    )

    registrations = get_workflow_pack_registry_store().list_registrations()
    validate_workflow_pack_registrations(registrations)
    validate_workflow_pack_execution_bindings()
    validate_workflow_pack_queue_policies()
    return registrations


def _require_workflow_pack_registry_ready() -> None:
    status_descriptor = get_workflow_pack_registry_store_runtime_status()
    if status_descriptor.status is RuntimeReadinessStatus.READY:
        return
    raise WorkflowPackRegistryUnavailableError(
        "Workflow-pack registry store is not ready. "
        f"Current status is `{status_descriptor.status.value}`. {status_descriptor.detail}"
    )
