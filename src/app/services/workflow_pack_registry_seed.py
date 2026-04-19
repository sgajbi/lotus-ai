from __future__ import annotations

from app.contracts.workflow_packs import (
    WorkflowPackActivationState,
    WorkflowPackCallerIdentityClass,
    WorkflowPackDefinitionReferenceDescriptor,
    WorkflowPackDefinitionReferenceType,
    WorkflowPackEnvironment,
    WorkflowPackExecutionMode,
    WorkflowPackRegistrationDescriptor,
    WorkflowPackRegistrationStatus,
    WorkflowPackValidationRuleDescriptor,
)
from app.services.workflow_pack_phase1_specs import (
    ADVISOR_BRIEF_V1_SPEC,
    ADVISOR_BRIEF_V2_SPEC,
)


def build_seed_workflow_pack_registrations() -> list[WorkflowPackRegistrationDescriptor]:
    return [
        WorkflowPackRegistrationDescriptor(
            pack_id=ADVISOR_BRIEF_V1_SPEC.pack_id,
            pack_family=ADVISOR_BRIEF_V1_SPEC.pack_family,
            version=ADVISOR_BRIEF_V1_SPEC.version,
            owner_repository=ADVISOR_BRIEF_V1_SPEC.owner_repository,
            owner_service=ADVISOR_BRIEF_V1_SPEC.owner_service,
            truth_owner_services=list(ADVISOR_BRIEF_V1_SPEC.truth_owner_services),
            primary_use_case=ADVISOR_BRIEF_V1_SPEC.primary_use_case,
            workflow_authority_owner=ADVISOR_BRIEF_V1_SPEC.workflow_authority_owner,
            default_execution_mode=WorkflowPackExecutionMode.REVIEW_GATED,
            definition_ref="repo://lotus-gateway/src/app/contracts/advisor_brief.py",
            definition_refs=_advisor_brief_v1_definition_refs(),
            compatibility_contract_version="workflow-pack-contract.v1",
            registration_status=WorkflowPackRegistrationStatus.REGISTERED,
            activation_state=WorkflowPackActivationState.PILOT,
            registered_definition_digest="sha256:advisor-brief-v1-registered-digest",
            supported_callers=list(ADVISOR_BRIEF_V1_SPEC.supported_callers),
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
            surface_scope=list(ADVISOR_BRIEF_V1_SPEC.surface_scope),
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
            pack_id=ADVISOR_BRIEF_V2_SPEC.pack_id,
            pack_family=ADVISOR_BRIEF_V2_SPEC.pack_family,
            version=ADVISOR_BRIEF_V2_SPEC.version,
            owner_repository=ADVISOR_BRIEF_V2_SPEC.owner_repository,
            owner_service=ADVISOR_BRIEF_V2_SPEC.owner_service,
            truth_owner_services=list(ADVISOR_BRIEF_V2_SPEC.truth_owner_services),
            primary_use_case=ADVISOR_BRIEF_V2_SPEC.primary_use_case,
            workflow_authority_owner=ADVISOR_BRIEF_V2_SPEC.workflow_authority_owner,
            default_execution_mode=WorkflowPackExecutionMode.REVIEW_GATED,
            definition_ref="repo://lotus-gateway/src/app/services/advisor_brief_service.py",
            definition_refs=_advisor_brief_v2_definition_refs(),
            compatibility_contract_version="workflow-pack-contract.v1",
            registration_status=WorkflowPackRegistrationStatus.DISCOVERED,
            activation_state=WorkflowPackActivationState.DARK,
            registered_definition_digest="sha256:advisor-brief-v2-discovered-digest",
            supported_callers=list(ADVISOR_BRIEF_V2_SPEC.supported_callers),
            supported_identity_classes=[
                WorkflowPackCallerIdentityClass.INTERNAL_SERVICE,
            ],
            supported_environments=[WorkflowPackEnvironment.DEVELOPMENT],
            tenant_scope=[],
            surface_scope=list(ADVISOR_BRIEF_V2_SPEC.surface_scope),
            default_rollout_stage="DISCOVERY_ONLY",
            pause_state="NOT_PAUSED",
            supersedes=f"{ADVISOR_BRIEF_V1_SPEC.pack_id}@{ADVISOR_BRIEF_V1_SPEC.version}",
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


def build_workflow_pack_validation_rules() -> list[WorkflowPackValidationRuleDescriptor]:
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


def validate_workflow_pack_registrations(
    registrations: list[WorkflowPackRegistrationDescriptor],
) -> None:
    _validate_unique_registration_identity(registrations)
    _validate_registered_entries_have_scope(registrations)
    _validate_retired_entries_are_not_active(registrations)
    _validate_definition_references(registrations)


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
