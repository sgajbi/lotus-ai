from __future__ import annotations

from app.config import settings
from app.contracts.workflow_packs import (
    WorkflowPackActivationState,
    WorkflowPackCallerIdentityClass,
    WorkflowPackControlEventDescriptor,
    WorkflowPackDefinitionReferenceDescriptor,
    WorkflowPackDefinitionReferenceType,
    WorkflowPackEnvironment,
    WorkflowPackExecutionMode,
    WorkflowPackRegistrationDescriptor,
    WorkflowPackRegistrationDetailResponse,
    WorkflowPackRegistrationStatus,
    WorkflowPackRegistryCatalogResponse,
    WorkflowPackValidationRuleDescriptor,
)

_REGISTRATION_STATE: list[WorkflowPackRegistrationDescriptor] | None = None
_CONTROL_EVENTS: list[WorkflowPackControlEventDescriptor] = []


def build_workflow_pack_registry_catalog() -> WorkflowPackRegistryCatalogResponse:
    registrations = _validated_registrations()
    registered_count = sum(
        1
        for registration in registrations
        if registration.registration_status == WorkflowPackRegistrationStatus.REGISTERED
    )
    production_eligible_count = sum(
        1
        for registration in registrations
        if WorkflowPackEnvironment.PRODUCTION in registration.supported_environments
    )
    return WorkflowPackRegistryCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        phase=settings.delivery_phase,
        registration_count=len(registrations),
        registered_count=registered_count,
        production_eligible_count=production_eligible_count,
        registrations=registrations,
        validation_rules=_build_validation_rules(),
        status_summary=[
            "Workflow-pack registry records are modeled separately from capability-pack maturity so runtime activation can stay explicit and auditable.",
            "This slice keeps registration records read-only and catalog-backed so Lotus can harden control-plane truth before introducing mutable activation transitions.",
            "Only declared workflow-pack versions with valid ownership, scope, and definition references are eligible to advance into later activation-evaluation slices.",
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
        validation_rules=_build_validation_rules(),
        denied_without_registration=True,
        status_summary=[
            "Workflow-pack execution remains deny-by-default for versions that do not resolve through the governed registry.",
            "This record captures activation posture and ownership metadata without duplicating business workflow logic from the owning repository.",
        ],
    )


def get_workflow_pack_registration(
    *, pack_id: str, version: str
) -> WorkflowPackRegistrationDescriptor | None:
    for registration in _validated_registrations():
        if registration.pack_id == pack_id and registration.version == version:
            return registration
    return None


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
    _set_registration_state(updated_registrations)


def list_workflow_pack_control_events(
    *,
    pack_id: str | None = None,
    version: str | None = None,
    limit: int = 20,
) -> list[WorkflowPackControlEventDescriptor]:
    events = list(_CONTROL_EVENTS)
    if pack_id is not None:
        events = [event for event in events if event.pack_id == pack_id]
    if version is not None:
        events = [event for event in events if event.version == version]
    events.sort(key=lambda event: event.recorded_at, reverse=True)
    return events[: max(limit, 1)]


def append_workflow_pack_control_event(event: WorkflowPackControlEventDescriptor) -> None:
    _CONTROL_EVENTS.append(event)


def reset_workflow_pack_registry_state() -> None:
    global _REGISTRATION_STATE
    _REGISTRATION_STATE = None
    _CONTROL_EVENTS.clear()


def _validated_registrations() -> list[WorkflowPackRegistrationDescriptor]:
    registrations = _get_registration_state()
    _validate_unique_registration_identity(registrations)
    _validate_registered_entries_have_scope(registrations)
    _validate_retired_entries_are_not_active(registrations)
    _validate_definition_references(registrations)
    return registrations


def _get_registration_state() -> list[WorkflowPackRegistrationDescriptor]:
    global _REGISTRATION_STATE
    if _REGISTRATION_STATE is None:
        _REGISTRATION_STATE = _build_workflow_pack_registrations()
    return [registration.model_copy(deep=True) for registration in _REGISTRATION_STATE]


def _set_registration_state(
    registrations: list[WorkflowPackRegistrationDescriptor],
) -> None:
    global _REGISTRATION_STATE
    _validate_unique_registration_identity(registrations)
    _validate_registered_entries_have_scope(registrations)
    _validate_retired_entries_are_not_active(registrations)
    _validate_definition_references(registrations)
    _REGISTRATION_STATE = [registration.model_copy(deep=True) for registration in registrations]


def _build_workflow_pack_registrations() -> list[WorkflowPackRegistrationDescriptor]:
    return [
        WorkflowPackRegistrationDescriptor(
            pack_id="advisor_brief.pack",
            pack_family="advisor_brief",
            version="v1",
            owner_repository="lotus-gateway",
            owner_service="lotus-gateway",
            truth_owner_services=["lotus-gateway", "lotus-performance", "lotus-risk"],
            primary_use_case="advisor_brief",
            workflow_authority_owner="lotus-gateway",
            default_execution_mode=WorkflowPackExecutionMode.REVIEW_GATED,
            definition_ref="repo://lotus-gateway/src/app/contracts/advisor_brief.py",
            definition_refs=_advisor_brief_v1_definition_refs(),
            compatibility_contract_version="workflow-pack-contract.v1",
            registration_status=WorkflowPackRegistrationStatus.REGISTERED,
            activation_state=WorkflowPackActivationState.PILOT,
            registered_definition_digest="sha256:advisor-brief-v1-registered-digest",
            supported_callers=["lotus-gateway"],
            supported_identity_classes=[
                WorkflowPackCallerIdentityClass.INTERNAL_SERVICE,
                WorkflowPackCallerIdentityClass.BANKER_PRODUCT,
            ],
            supported_environments=[
                WorkflowPackEnvironment.DEVELOPMENT,
                WorkflowPackEnvironment.QA,
                WorkflowPackEnvironment.UAT,
            ],
            tenant_scope=[],
            surface_scope=["advisor-brief-panel", "advisor-brief-workspace"],
            default_rollout_stage="PILOT_SCOPED",
            pause_state="NOT_PAUSED",
            supersedes=None,
            superseded_by=None,
            registered_at="2026-04-18T08:00:00Z",
            registered_by="lotus-ai.workflow-pack-registry.seed",
            last_activated_at="2026-04-18T08:30:00Z",
            last_changed_at="2026-04-18T08:30:00Z",
            status_summary=[
                "The advisor-brief workflow pack is the first bounded reference family for the governed registry path.",
                "Activation remains pilot-scoped outside production while Lotus proves registry truth, ownership metadata, owning-repository evidence, and caller scoping before broader rollout.",
            ],
        ),
        WorkflowPackRegistrationDescriptor(
            pack_id="advisor_brief.pack",
            pack_family="advisor_brief",
            version="v2",
            owner_repository="lotus-gateway",
            owner_service="lotus-gateway",
            truth_owner_services=["lotus-gateway", "lotus-performance", "lotus-risk"],
            primary_use_case="advisor_brief",
            workflow_authority_owner="lotus-gateway",
            default_execution_mode=WorkflowPackExecutionMode.REVIEW_GATED,
            definition_ref="repo://lotus-gateway/src/app/services/advisor_brief_service.py",
            definition_refs=_advisor_brief_v2_definition_refs(),
            compatibility_contract_version="workflow-pack-contract.v1",
            registration_status=WorkflowPackRegistrationStatus.DISCOVERED,
            activation_state=WorkflowPackActivationState.DARK,
            registered_definition_digest="sha256:advisor-brief-v2-discovered-digest",
            supported_callers=["lotus-gateway"],
            supported_identity_classes=[
                WorkflowPackCallerIdentityClass.INTERNAL_SERVICE,
            ],
            supported_environments=[WorkflowPackEnvironment.DEVELOPMENT],
            tenant_scope=[],
            surface_scope=["advisor-brief-panel"],
            default_rollout_stage="DISCOVERY_ONLY",
            pause_state="NOT_PAUSED",
            supersedes="advisor_brief.pack@v1",
            superseded_by=None,
            registered_at="2026-04-18T09:00:00Z",
            registered_by="lotus-ai.workflow-pack-registry.seed",
            last_activated_at=None,
            last_changed_at="2026-04-18T09:00:00Z",
            status_summary=[
                "A discovered successor version is visible in the registry without being treated as runtime-eligible.",
                "Keeping the candidate dark prevents implicit default-version drift before version-specific owner artifacts and broader rollout review exist.",
            ],
        ),
    ]


def _advisor_brief_v1_definition_refs() -> list[WorkflowPackDefinitionReferenceDescriptor]:
    return [
        _definition_ref(
            reference_id="primary_contract",
            repository="lotus-gateway",
            path="src/app/contracts/advisor_brief.py",
            reference_type=WorkflowPackDefinitionReferenceType.CONTRACT,
            required_for_registration=True,
            description="Source-grounded advisor-brief response contract owned by the gateway composition layer.",
        ),
        _definition_ref(
            reference_id="owner_service",
            repository="lotus-gateway",
            path="src/app/services/advisor_brief_service.py",
            reference_type=WorkflowPackDefinitionReferenceType.SERVICE,
            required_for_registration=True,
            description="Gateway service that assembles advisor-brief facts and invokes bounded lotus-ai generation.",
        ),
        _definition_ref(
            reference_id="owner_router",
            repository="lotus-gateway",
            path="src/app/routers/workbench.py",
            reference_type=WorkflowPackDefinitionReferenceType.ROUTER,
            required_for_registration=True,
            description="Workbench-facing route that exposes the governed advisor-brief surface.",
        ),
        _definition_ref(
            reference_id="owner_tests",
            repository="lotus-gateway",
            path="tests/unit/test_advisor_brief_service.py",
            reference_type=WorkflowPackDefinitionReferenceType.TEST,
            required_for_registration=True,
            description="Owner-repository regression coverage for advisor-brief contract and service behavior.",
        ),
        _definition_ref(
            reference_id="ui_rfc",
            repository="lotus-workbench",
            path="docs/rfcs/RFC-0020-ai-advisor-brief-copilot.md",
            reference_type=WorkflowPackDefinitionReferenceType.RFC,
            required_for_registration=False,
            description="UI and product RFC describing the advisor-brief product surface that consumes the gateway contract.",
        ),
        _definition_ref(
            reference_id="ui_validation",
            repository="lotus-workbench",
            path="scripts/live/validation/contract-metadata.mjs",
            reference_type=WorkflowPackDefinitionReferenceType.VALIDATION,
            required_for_registration=False,
            description="Canonical front-office validation metadata proving the advisor-brief surface remains visible and governed.",
        ),
    ]


def _advisor_brief_v2_definition_refs() -> list[WorkflowPackDefinitionReferenceDescriptor]:
    return [
        _definition_ref(
            reference_id="primary_service_candidate",
            repository="lotus-gateway",
            path="src/app/services/advisor_brief_service.py",
            reference_type=WorkflowPackDefinitionReferenceType.SERVICE,
            required_for_registration=True,
            description="Current owner-service implementation that a successor advisor-brief pack version would extend or replace.",
        ),
        _definition_ref(
            reference_id="contract_anchor",
            repository="lotus-gateway",
            path="src/app/contracts/advisor_brief.py",
            reference_type=WorkflowPackDefinitionReferenceType.CONTRACT,
            required_for_registration=True,
            description="Current owner contract that constrains discovered successor work until a version-specific contract lands.",
        ),
        _definition_ref(
            reference_id="owner_tests",
            repository="lotus-gateway",
            path="tests/unit/test_advisor_brief_service.py",
            reference_type=WorkflowPackDefinitionReferenceType.TEST,
            required_for_registration=True,
            description="Regression suite that must stay green before a discovered successor may advance out of dark posture.",
        ),
        _definition_ref(
            reference_id="ui_rfc",
            repository="lotus-workbench",
            path="docs/rfcs/RFC-0020-ai-advisor-brief-copilot.md",
            reference_type=WorkflowPackDefinitionReferenceType.RFC,
            required_for_registration=False,
            description="Product-level advisor-brief RFC that remains relevant while successor onboarding stays in discovery.",
        ),
    ]


def _definition_ref(
    *,
    reference_id: str,
    repository: str,
    path: str,
    reference_type: WorkflowPackDefinitionReferenceType,
    required_for_registration: bool,
    description: str,
) -> WorkflowPackDefinitionReferenceDescriptor:
    return WorkflowPackDefinitionReferenceDescriptor(
        reference_id=reference_id,
        repository=repository,
        path=path,
        reference_type=reference_type,
        required_for_registration=required_for_registration,
        description=description,
    )


def _build_validation_rules() -> list[WorkflowPackValidationRuleDescriptor]:
    return [
        WorkflowPackValidationRuleDescriptor(
            rule_id="unique_pack_version_identity",
            description="Each workflow-pack registration must have a unique pack_id and version pair.",
        ),
        WorkflowPackValidationRuleDescriptor(
            rule_id="registered_entries_require_scope",
            description="REGISTERED workflow-pack versions must declare at least one supported caller and one supported environment.",
        ),
        WorkflowPackValidationRuleDescriptor(
            rule_id="retired_entries_cannot_remain_active",
            description="A RETIRED workflow-pack version cannot keep an activation state other than RETIRED.",
        ),
        WorkflowPackValidationRuleDescriptor(
            rule_id="definition_refs_ground_registry_truth",
            description="Each workflow-pack registration must declare a primary repo reference, include structured owner artifacts, and keep at least one required reference in the owning repository.",
        ),
    ]


def _validate_unique_registration_identity(
    registrations: list[WorkflowPackRegistrationDescriptor],
) -> None:
    seen: set[tuple[str, str]] = set()
    for registration in registrations:
        identity = (registration.pack_id, registration.version)
        if identity in seen:
            raise ValueError(
                f"Duplicate workflow-pack registration identity: {registration.pack_id}@{registration.version}"
            )
        seen.add(identity)


def _validate_registered_entries_have_scope(
    registrations: list[WorkflowPackRegistrationDescriptor],
) -> None:
    for registration in registrations:
        if registration.registration_status != WorkflowPackRegistrationStatus.REGISTERED:
            continue
        if not registration.supported_callers or not registration.supported_environments:
            raise ValueError(
                f"Registered workflow-pack missing execution scope: {registration.pack_id}@{registration.version}"
            )


def _validate_retired_entries_are_not_active(
    registrations: list[WorkflowPackRegistrationDescriptor],
) -> None:
    for registration in registrations:
        if registration.registration_status != WorkflowPackRegistrationStatus.RETIRED:
            continue
        if registration.activation_state != WorkflowPackActivationState.RETIRED:
            raise ValueError(
                f"Retired workflow-pack cannot remain active: {registration.pack_id}@{registration.version}"
            )


def _validate_definition_references(
    registrations: list[WorkflowPackRegistrationDescriptor],
) -> None:
    for registration in registrations:
        if not registration.definition_ref.startswith("repo://"):
            raise ValueError(
                f"Workflow-pack registration definition_ref must use repo:// form: {registration.pack_id}@{registration.version}"
            )
        if not registration.definition_refs:
            raise ValueError(
                f"Workflow-pack registration missing definition_refs: {registration.pack_id}@{registration.version}"
            )
        structured_refs = [
            f"repo://{definition_ref.repository}/{definition_ref.path}"
            for definition_ref in registration.definition_refs
        ]
        if registration.definition_ref not in structured_refs:
            raise ValueError(
                f"Workflow-pack registration primary definition_ref must match one structured definition ref: {registration.pack_id}@{registration.version}"
            )
        required_refs = [
            definition_ref
            for definition_ref in registration.definition_refs
            if definition_ref.required_for_registration
        ]
        if not required_refs:
            raise ValueError(
                f"Workflow-pack registration missing required owner artifacts: {registration.pack_id}@{registration.version}"
            )
        if not any(
            definition_ref.repository == registration.owner_repository
            for definition_ref in required_refs
        ):
            raise ValueError(
                f"Workflow-pack registration must keep at least one required owner artifact in owner_repository: {registration.pack_id}@{registration.version}"
            )
