from __future__ import annotations

from app.config import settings
from app.contracts.workflow_packs import (
    WorkflowPackActivationState,
    WorkflowPackCallerIdentityClass,
    WorkflowPackEnvironment,
    WorkflowPackExecutionMode,
    WorkflowPackRegistrationDescriptor,
    WorkflowPackRegistrationDetailResponse,
    WorkflowPackRegistrationStatus,
    WorkflowPackRegistryCatalogResponse,
    WorkflowPackValidationRuleDescriptor,
)


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


def _validated_registrations() -> list[WorkflowPackRegistrationDescriptor]:
    registrations = _build_workflow_pack_registrations()
    _validate_unique_registration_identity(registrations)
    _validate_registered_entries_have_scope(registrations)
    _validate_retired_entries_are_not_active(registrations)
    return registrations


def _build_workflow_pack_registrations() -> list[WorkflowPackRegistrationDescriptor]:
    return [
        WorkflowPackRegistrationDescriptor(
            pack_id="advisor_brief.pack",
            pack_family="advisor_brief",
            version="v1",
            owner_repository="lotus-manage",
            owner_service="lotus-gateway",
            truth_owner_services=["lotus-manage", "lotus-performance", "lotus-risk"],
            primary_use_case="advisor_brief",
            workflow_authority_owner="lotus-gateway",
            default_execution_mode=WorkflowPackExecutionMode.REVIEW_GATED,
            definition_ref="repo://lotus-manage/docs/ai/workflow-packs/advisor_brief/v1",
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
                "Activation remains pilot-scoped outside production while Lotus proves registry truth, ownership metadata, and caller scoping before broader rollout.",
            ],
        ),
        WorkflowPackRegistrationDescriptor(
            pack_id="advisor_brief.pack",
            pack_family="advisor_brief",
            version="v2",
            owner_repository="lotus-manage",
            owner_service="lotus-gateway",
            truth_owner_services=["lotus-manage", "lotus-performance", "lotus-risk"],
            primary_use_case="advisor_brief",
            workflow_authority_owner="lotus-gateway",
            default_execution_mode=WorkflowPackExecutionMode.REVIEW_GATED,
            definition_ref="repo://lotus-manage/docs/ai/workflow-packs/advisor_brief/v2",
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
                "Keeping the candidate dark prevents implicit default-version drift before validation and broader rollout review exist.",
            ],
        ),
    ]


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
