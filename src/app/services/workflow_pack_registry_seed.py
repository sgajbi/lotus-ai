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
    DPM_EXCEPTION_SUMMARY_V1_SPEC,
    DPM_OPERATIONS_HANDOFF_SUMMARY_V1_SPEC,
    DPM_WAVE_PM_MEMO_V1_SPEC,
    OUTCOME_REVIEW_NARRATIVE_V1_SPEC,
    PROOF_PACK_PM_MEMO_V1_SPEC,
    TWR_INSPECTION_SUPPORT_BRIEF_V1_SPEC,
    WORKSPACE_RATIONALE_V1_SPEC,
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
        WorkflowPackRegistrationDescriptor(
            pack_id=WORKSPACE_RATIONALE_V1_SPEC.pack_id,
            pack_family=WORKSPACE_RATIONALE_V1_SPEC.pack_family,
            version=WORKSPACE_RATIONALE_V1_SPEC.version,
            owner_repository=WORKSPACE_RATIONALE_V1_SPEC.owner_repository,
            owner_service=WORKSPACE_RATIONALE_V1_SPEC.owner_service,
            truth_owner_services=list(WORKSPACE_RATIONALE_V1_SPEC.truth_owner_services),
            primary_use_case=WORKSPACE_RATIONALE_V1_SPEC.primary_use_case,
            workflow_authority_owner=WORKSPACE_RATIONALE_V1_SPEC.workflow_authority_owner,
            default_execution_mode=WorkflowPackExecutionMode.REVIEW_GATED,
            definition_ref="repo://lotus-advise/src/api/workspaces/router.py",
            definition_refs=_workspace_rationale_v1_definition_refs(),
            compatibility_contract_version="workflow-pack-contract.v1",
            registration_status=WorkflowPackRegistrationStatus.REGISTERED,
            activation_state=WorkflowPackActivationState.PILOT,
            registered_definition_digest="sha256:workspace-rationale-v1-registered-digest",
            supported_callers=list(WORKSPACE_RATIONALE_V1_SPEC.supported_callers),
            supported_identity_classes=[
                WorkflowPackCallerIdentityClass.INTERNAL_SERVICE,
            ],
            supported_environments=[
                WorkflowPackEnvironment.DEVELOPMENT,
                WorkflowPackEnvironment.QA,
                WorkflowPackEnvironment.UAT,
            ],
            tenant_scope=[],
            surface_scope=list(WORKSPACE_RATIONALE_V1_SPEC.surface_scope),
            default_rollout_stage="PILOT_SCOPED",
            pause_state="NOT_PAUSED",
            supersedes=None,
            superseded_by=None,
            registered_at="2026-04-20T10:00:00Z",
            registered_by="lotus-ai.workflow-pack-registry.seed",
            last_activated_at="2026-04-20T10:15:00Z",
            last_changed_at="2026-04-20T10:15:00Z",
            status_summary=[
                "The advisory workspace rationale workflow pack extends executable workflow-pack proof into a domain-owned advisory surface.",
                "Activation remains pilot-scoped while Lotus validates the lotus-advise-owned rationale seam against explicit run-ledger and registration truth.",
            ],
        ),
        WorkflowPackRegistrationDescriptor(
            pack_id=TWR_INSPECTION_SUPPORT_BRIEF_V1_SPEC.pack_id,
            pack_family=TWR_INSPECTION_SUPPORT_BRIEF_V1_SPEC.pack_family,
            version=TWR_INSPECTION_SUPPORT_BRIEF_V1_SPEC.version,
            owner_repository=TWR_INSPECTION_SUPPORT_BRIEF_V1_SPEC.owner_repository,
            owner_service=TWR_INSPECTION_SUPPORT_BRIEF_V1_SPEC.owner_service,
            truth_owner_services=list(TWR_INSPECTION_SUPPORT_BRIEF_V1_SPEC.truth_owner_services),
            primary_use_case=TWR_INSPECTION_SUPPORT_BRIEF_V1_SPEC.primary_use_case,
            workflow_authority_owner=TWR_INSPECTION_SUPPORT_BRIEF_V1_SPEC.workflow_authority_owner,
            default_execution_mode=WorkflowPackExecutionMode.REVIEW_GATED,
            definition_ref="repo://lotus-performance/app/api/endpoints/inspections.py",
            definition_refs=_twr_inspection_support_brief_v1_definition_refs(),
            compatibility_contract_version="workflow-pack-contract.v1",
            registration_status=WorkflowPackRegistrationStatus.REGISTERED,
            activation_state=WorkflowPackActivationState.PILOT,
            registered_definition_digest="sha256:twr-inspection-support-brief-v1-registered-digest",
            supported_callers=list(TWR_INSPECTION_SUPPORT_BRIEF_V1_SPEC.supported_callers),
            supported_identity_classes=[
                WorkflowPackCallerIdentityClass.INTERNAL_SERVICE,
            ],
            supported_environments=[
                WorkflowPackEnvironment.DEVELOPMENT,
                WorkflowPackEnvironment.QA,
                WorkflowPackEnvironment.UAT,
            ],
            tenant_scope=[],
            surface_scope=list(TWR_INSPECTION_SUPPORT_BRIEF_V1_SPEC.surface_scope),
            default_rollout_stage="PILOT_SCOPED",
            pause_state="NOT_PAUSED",
            supersedes=None,
            superseded_by=None,
            registered_at="2026-04-20T18:00:00Z",
            registered_by="lotus-ai.workflow-pack-registry.seed",
            last_activated_at="2026-04-20T18:20:00Z",
            last_changed_at="2026-04-20T18:20:00Z",
            status_summary=[
                "The TWR inspection support-brief workflow pack extends executable workflow-pack proof into a domain-owned performance supportability surface.",
                "Activation remains pilot-scoped while Lotus validates support-brief generation against the inspection evidence contract and bounded run-ledger posture.",
            ],
        ),
        WorkflowPackRegistrationDescriptor(
            pack_id=PROOF_PACK_PM_MEMO_V1_SPEC.pack_id,
            pack_family=PROOF_PACK_PM_MEMO_V1_SPEC.pack_family,
            version=PROOF_PACK_PM_MEMO_V1_SPEC.version,
            owner_repository=PROOF_PACK_PM_MEMO_V1_SPEC.owner_repository,
            owner_service=PROOF_PACK_PM_MEMO_V1_SPEC.owner_service,
            truth_owner_services=list(PROOF_PACK_PM_MEMO_V1_SPEC.truth_owner_services),
            primary_use_case=PROOF_PACK_PM_MEMO_V1_SPEC.primary_use_case,
            workflow_authority_owner=PROOF_PACK_PM_MEMO_V1_SPEC.workflow_authority_owner,
            default_execution_mode=WorkflowPackExecutionMode.REVIEW_GATED,
            definition_ref="repo://lotus-manage/src/core/proof_packs/handoffs.py",
            definition_refs=_proof_pack_pm_memo_v1_definition_refs(),
            compatibility_contract_version="workflow-pack-contract.v1",
            registration_status=WorkflowPackRegistrationStatus.REGISTERED,
            activation_state=WorkflowPackActivationState.PILOT,
            registered_definition_digest="sha256:dpm-pm-memo-v1-registered-digest",
            supported_callers=list(PROOF_PACK_PM_MEMO_V1_SPEC.supported_callers),
            supported_identity_classes=[
                WorkflowPackCallerIdentityClass.INTERNAL_SERVICE,
            ],
            supported_environments=[
                WorkflowPackEnvironment.DEVELOPMENT,
                WorkflowPackEnvironment.QA,
                WorkflowPackEnvironment.UAT,
            ],
            tenant_scope=[],
            surface_scope=list(PROOF_PACK_PM_MEMO_V1_SPEC.surface_scope),
            default_rollout_stage="PILOT_SCOPED",
            pause_state="NOT_PAUSED",
            supersedes=None,
            superseded_by=None,
            registered_at="2026-05-07T08:00:00Z",
            registered_by="lotus-ai.workflow-pack-registry.seed",
            last_activated_at="2026-05-07T08:20:00Z",
            last_changed_at="2026-05-07T08:20:00Z",
            status_summary=[
                "The DPM PM memo workflow pack consumes lotus-manage DpmProofPackAiEvidenceInput only.",
                "Activation remains pilot-scoped while Gateway and Workbench product surfaces add unavailable fallback, memo review posture, and canonical proof without browser-side prompt construction.",
            ],
        ),
        WorkflowPackRegistrationDescriptor(
            pack_id=OUTCOME_REVIEW_NARRATIVE_V1_SPEC.pack_id,
            pack_family=OUTCOME_REVIEW_NARRATIVE_V1_SPEC.pack_family,
            version=OUTCOME_REVIEW_NARRATIVE_V1_SPEC.version,
            owner_repository=OUTCOME_REVIEW_NARRATIVE_V1_SPEC.owner_repository,
            owner_service=OUTCOME_REVIEW_NARRATIVE_V1_SPEC.owner_service,
            truth_owner_services=list(OUTCOME_REVIEW_NARRATIVE_V1_SPEC.truth_owner_services),
            primary_use_case=OUTCOME_REVIEW_NARRATIVE_V1_SPEC.primary_use_case,
            workflow_authority_owner=OUTCOME_REVIEW_NARRATIVE_V1_SPEC.workflow_authority_owner,
            default_execution_mode=WorkflowPackExecutionMode.REVIEW_GATED,
            definition_ref="repo://lotus-manage/src/core/outcomes/handoffs.py",
            definition_refs=_outcome_review_narrative_v1_definition_refs(),
            compatibility_contract_version="workflow-pack-contract.v1",
            registration_status=WorkflowPackRegistrationStatus.REGISTERED,
            activation_state=WorkflowPackActivationState.PILOT,
            registered_definition_digest="sha256:outcome-review-narrative-v1-registered-digest",
            supported_callers=list(OUTCOME_REVIEW_NARRATIVE_V1_SPEC.supported_callers),
            supported_identity_classes=[
                WorkflowPackCallerIdentityClass.INTERNAL_SERVICE,
            ],
            supported_environments=[
                WorkflowPackEnvironment.DEVELOPMENT,
                WorkflowPackEnvironment.QA,
                WorkflowPackEnvironment.UAT,
            ],
            tenant_scope=[],
            surface_scope=list(OUTCOME_REVIEW_NARRATIVE_V1_SPEC.surface_scope),
            default_rollout_stage="PILOT_SCOPED",
            pause_state="NOT_PAUSED",
            supersedes=None,
            superseded_by=None,
            registered_at="2026-05-05T08:00:00Z",
            registered_by="lotus-ai.workflow-pack-registry.seed",
            last_activated_at="2026-05-05T08:20:00Z",
            last_changed_at="2026-05-05T08:20:00Z",
            status_summary=[
                "The outcome-review narrative workflow pack consumes lotus-manage DpmOutcomeAiEvidenceInput only.",
                "Activation remains pilot-scoped while Gateway and Workbench product surfaces are implemented after the lotus-ai contract proves guardrails, provenance, and review-gated run posture.",
            ],
        ),
        WorkflowPackRegistrationDescriptor(
            pack_id=DPM_WAVE_PM_MEMO_V1_SPEC.pack_id,
            pack_family=DPM_WAVE_PM_MEMO_V1_SPEC.pack_family,
            version=DPM_WAVE_PM_MEMO_V1_SPEC.version,
            owner_repository=DPM_WAVE_PM_MEMO_V1_SPEC.owner_repository,
            owner_service=DPM_WAVE_PM_MEMO_V1_SPEC.owner_service,
            truth_owner_services=list(DPM_WAVE_PM_MEMO_V1_SPEC.truth_owner_services),
            primary_use_case=DPM_WAVE_PM_MEMO_V1_SPEC.primary_use_case,
            workflow_authority_owner=DPM_WAVE_PM_MEMO_V1_SPEC.workflow_authority_owner,
            default_execution_mode=WorkflowPackExecutionMode.REVIEW_GATED,
            definition_ref="repo://lotus-manage/src/core/waves/handoffs.py",
            definition_refs=_dpm_wave_pm_memo_v1_definition_refs(),
            compatibility_contract_version="workflow-pack-contract.v1",
            registration_status=WorkflowPackRegistrationStatus.REGISTERED,
            activation_state=WorkflowPackActivationState.PILOT,
            registered_definition_digest="sha256:dpm-wave-pm-memo-v1-registered-digest",
            supported_callers=list(DPM_WAVE_PM_MEMO_V1_SPEC.supported_callers),
            supported_identity_classes=[
                WorkflowPackCallerIdentityClass.INTERNAL_SERVICE,
            ],
            supported_environments=[
                WorkflowPackEnvironment.DEVELOPMENT,
                WorkflowPackEnvironment.QA,
                WorkflowPackEnvironment.UAT,
            ],
            tenant_scope=[],
            surface_scope=list(DPM_WAVE_PM_MEMO_V1_SPEC.surface_scope),
            default_rollout_stage="PILOT_SCOPED",
            pause_state="NOT_PAUSED",
            supersedes=None,
            superseded_by=None,
            registered_at="2026-05-08T08:00:00Z",
            registered_by="lotus-ai.workflow-pack-registry.seed",
            last_activated_at="2026-05-08T08:20:00Z",
            last_changed_at="2026-05-08T08:20:00Z",
            status_summary=[
                "The DPM wave PM memo workflow pack consumes lotus-manage DpmWaveReportInput only.",
                "Activation remains pilot-scoped while Gateway and Workbench add product-surface invocation, unavailable posture, and canonical live proof without reconstructing wave or proof-pack evidence.",
            ],
        ),
        WorkflowPackRegistrationDescriptor(
            pack_id=DPM_EXCEPTION_SUMMARY_V1_SPEC.pack_id,
            pack_family=DPM_EXCEPTION_SUMMARY_V1_SPEC.pack_family,
            version=DPM_EXCEPTION_SUMMARY_V1_SPEC.version,
            owner_repository=DPM_EXCEPTION_SUMMARY_V1_SPEC.owner_repository,
            owner_service=DPM_EXCEPTION_SUMMARY_V1_SPEC.owner_service,
            truth_owner_services=list(DPM_EXCEPTION_SUMMARY_V1_SPEC.truth_owner_services),
            primary_use_case=DPM_EXCEPTION_SUMMARY_V1_SPEC.primary_use_case,
            workflow_authority_owner=DPM_EXCEPTION_SUMMARY_V1_SPEC.workflow_authority_owner,
            default_execution_mode=WorkflowPackExecutionMode.REVIEW_GATED,
            definition_ref="repo://lotus-manage/src/api/routers/monitoring.py",
            definition_refs=_dpm_exception_summary_v1_definition_refs(),
            compatibility_contract_version="workflow-pack-contract.v1",
            registration_status=WorkflowPackRegistrationStatus.REGISTERED,
            activation_state=WorkflowPackActivationState.PILOT,
            registered_definition_digest="sha256:dpm-exception-summary-v1-registered-digest",
            supported_callers=list(DPM_EXCEPTION_SUMMARY_V1_SPEC.supported_callers),
            supported_identity_classes=[
                WorkflowPackCallerIdentityClass.INTERNAL_SERVICE,
            ],
            supported_environments=[
                WorkflowPackEnvironment.DEVELOPMENT,
                WorkflowPackEnvironment.QA,
                WorkflowPackEnvironment.UAT,
            ],
            tenant_scope=[],
            surface_scope=list(DPM_EXCEPTION_SUMMARY_V1_SPEC.surface_scope),
            default_rollout_stage="PILOT_SCOPED",
            pause_state="NOT_PAUSED",
            supersedes=None,
            superseded_by=None,
            registered_at="2026-05-12T08:00:00Z",
            registered_by="lotus-ai.workflow-pack-registry.seed",
            last_activated_at="2026-05-12T08:20:00Z",
            last_changed_at="2026-05-12T08:20:00Z",
            status_summary=[
                "The DPM exception summary workflow pack consumes bounded lotus-manage monitoring exception evidence only.",
                "Activation remains pilot-scoped while product invocation and any broader copilot workspace are implemented by their owners without reconstructing exception truth.",
            ],
        ),
        WorkflowPackRegistrationDescriptor(
            pack_id=DPM_OPERATIONS_HANDOFF_SUMMARY_V1_SPEC.pack_id,
            pack_family=DPM_OPERATIONS_HANDOFF_SUMMARY_V1_SPEC.pack_family,
            version=DPM_OPERATIONS_HANDOFF_SUMMARY_V1_SPEC.version,
            owner_repository=DPM_OPERATIONS_HANDOFF_SUMMARY_V1_SPEC.owner_repository,
            owner_service=DPM_OPERATIONS_HANDOFF_SUMMARY_V1_SPEC.owner_service,
            truth_owner_services=list(DPM_OPERATIONS_HANDOFF_SUMMARY_V1_SPEC.truth_owner_services),
            primary_use_case=DPM_OPERATIONS_HANDOFF_SUMMARY_V1_SPEC.primary_use_case,
            workflow_authority_owner=(
                DPM_OPERATIONS_HANDOFF_SUMMARY_V1_SPEC.workflow_authority_owner
            ),
            default_execution_mode=WorkflowPackExecutionMode.REVIEW_GATED,
            definition_ref="repo://lotus-manage/src/core/waves/handoffs.py",
            definition_refs=_dpm_operations_handoff_summary_v1_definition_refs(),
            compatibility_contract_version="workflow-pack-contract.v1",
            registration_status=WorkflowPackRegistrationStatus.REGISTERED,
            activation_state=WorkflowPackActivationState.PILOT,
            registered_definition_digest=(
                "sha256:dpm-operations-handoff-summary-v1-registered-digest"
            ),
            supported_callers=list(DPM_OPERATIONS_HANDOFF_SUMMARY_V1_SPEC.supported_callers),
            supported_identity_classes=[
                WorkflowPackCallerIdentityClass.INTERNAL_SERVICE,
            ],
            supported_environments=[
                WorkflowPackEnvironment.DEVELOPMENT,
                WorkflowPackEnvironment.QA,
                WorkflowPackEnvironment.UAT,
            ],
            tenant_scope=[],
            surface_scope=list(DPM_OPERATIONS_HANDOFF_SUMMARY_V1_SPEC.surface_scope),
            default_rollout_stage="PILOT_SCOPED",
            pause_state="NOT_PAUSED",
            supersedes=None,
            superseded_by=None,
            registered_at="2026-05-11T08:00:00Z",
            registered_by="lotus-ai.workflow-pack-registry.seed",
            last_activated_at="2026-05-11T08:20:00Z",
            last_changed_at="2026-05-11T08:20:00Z",
            status_summary=[
                "The DPM operations handoff summary workflow pack consumes lotus-manage DpmWaveReportInput handoff evidence only.",
                "Activation remains pilot-scoped while Gateway and Workbench product surfaces add invocation, unavailable posture, and canonical live proof without reconstructing handoff or proof-pack evidence.",
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


def _workspace_rationale_v1_definition_refs() -> list[WorkflowPackDefinitionReferenceDescriptor]:
    return [
        _definition_ref(
            reference_id="owner_router",
            repository="lotus-advise",
            path="src/api/workspaces/router.py",
            reference_type=WorkflowPackDefinitionReferenceType.ROUTER,
            required_for_registration=True,
            description="Advisory workspace route that owns the rationale product surface.",
        ),
        _definition_ref(
            reference_id="owner_service",
            repository="lotus-advise",
            path="src/api/services/workspace_ai_service.py",
            reference_type=WorkflowPackDefinitionReferenceType.SERVICE,
            required_for_registration=True,
            description="Advisory service that assembles the bounded evidence bundle and calls lotus-ai.",
        ),
        _definition_ref(
            reference_id="owner_integration",
            repository="lotus-advise",
            path="src/integrations/lotus_ai/rationale.py",
            reference_type=WorkflowPackDefinitionReferenceType.SERVICE,
            required_for_registration=True,
            description="Lotus-advise integration seam that maps the workspace rationale flow onto the explicit workflow-pack execution route.",
        ),
        _definition_ref(
            reference_id="owner_tests",
            repository="lotus-advise",
            path="tests/unit/advisory/api/test_api_workspace.py",
            reference_type=WorkflowPackDefinitionReferenceType.TEST,
            required_for_registration=True,
            description="Owner-repository regression coverage for advisory workspace rationale behavior and degraded paths.",
        ),
        _definition_ref(
            reference_id="owner_context",
            repository="lotus-advise",
            path="REPOSITORY-ENGINEERING-CONTEXT.md",
            reference_type=WorkflowPackDefinitionReferenceType.CONTRACT,
            required_for_registration=False,
            description="Repository-local engineering context describing advisory ownership and runtime boundaries for the rationale surface.",
        ),
    ]


def _twr_inspection_support_brief_v1_definition_refs() -> list[
    WorkflowPackDefinitionReferenceDescriptor
]:
    return [
        _definition_ref(
            reference_id="owner_router",
            repository="lotus-performance",
            path="app/api/endpoints/inspections.py",
            reference_type=WorkflowPackDefinitionReferenceType.ROUTER,
            required_for_registration=True,
            description="TWR inspection endpoint family that owns the supportability inspection product surface.",
        ),
        _definition_ref(
            reference_id="owner_service",
            repository="lotus-performance",
            path="app/services/inspection/twr_inspection_service.py",
            reference_type=WorkflowPackDefinitionReferenceType.SERVICE,
            required_for_registration=True,
            description="Inspection service that synthesizes findings, artifacts, and the optional support brief.",
        ),
        _definition_ref(
            reference_id="owner_artifact_service",
            repository="lotus-performance",
            path="app/services/inspection/artifact_service.py",
            reference_type=WorkflowPackDefinitionReferenceType.SERVICE,
            required_for_registration=True,
            description="Inspection artifact service that persists supportability evidence artifacts including support-brief payloads.",
        ),
        _definition_ref(
            reference_id="owner_tests",
            repository="lotus-performance",
            path="tests/integration/test_inspections_api.py",
            reference_type=WorkflowPackDefinitionReferenceType.TEST,
            required_for_registration=True,
            description="Owner-repository regression coverage for TWR inspection contract and artifact behavior.",
        ),
        _definition_ref(
            reference_id="owner_rfc",
            repository="lotus-performance",
            path="docs/RFCs/RFC 045 - TWR Inspection and Supportability Contract.md",
            reference_type=WorkflowPackDefinitionReferenceType.RFC,
            required_for_registration=False,
            description="TWR inspection RFC that defines optional support-brief artifacts within the inspection contract family.",
        ),
    ]


def _proof_pack_pm_memo_v1_definition_refs() -> list[WorkflowPackDefinitionReferenceDescriptor]:
    return [
        _definition_ref(
            reference_id="primary_contract",
            repository="lotus-manage",
            path="src/core/proof_packs/handoffs.py",
            reference_type=WorkflowPackDefinitionReferenceType.CONTRACT,
            required_for_registration=True,
            description="Manage-owned DpmProofPackAiEvidenceInput contract that bounds proof-pack evidence for PM memo drafting.",
        ),
        _definition_ref(
            reference_id="owner_service",
            repository="lotus-manage",
            path="src/api/services/proof_pack_service.py",
            reference_type=WorkflowPackDefinitionReferenceType.SERVICE,
            required_for_registration=True,
            description="Manage service that materializes immutable proof packs and deterministic AI evidence input without generating AI narrative locally.",
        ),
        _definition_ref(
            reference_id="owner_router",
            repository="lotus-manage",
            path="src/api/routers/proof_packs.py",
            reference_type=WorkflowPackDefinitionReferenceType.ROUTER,
            required_for_registration=True,
            description="Manage API route exposing bounded proof-pack AI evidence input for downstream AI execution.",
        ),
        _definition_ref(
            reference_id="owner_tests",
            repository="lotus-manage",
            path="tests/unit/dpm/proof_packs/test_proof_pack_handoffs.py",
            reference_type=WorkflowPackDefinitionReferenceType.TEST,
            required_for_registration=True,
            description="Manage regression coverage proving forbidden fields and actions are removed from proof-pack AI evidence.",
        ),
        _definition_ref(
            reference_id="owner_rfc",
            repository="lotus-manage",
            path="docs/rfcs/RFC-0043-governed-ai-pm-copilot-for-dpm.md",
            reference_type=WorkflowPackDefinitionReferenceType.RFC,
            required_for_registration=False,
            description="RFC-0043 defines governed DPM PM memo support, no-domain-decision guardrails, review posture, and unavailable behavior.",
        ),
    ]


def _outcome_review_narrative_v1_definition_refs() -> list[
    WorkflowPackDefinitionReferenceDescriptor
]:
    return [
        _definition_ref(
            reference_id="primary_contract",
            repository="lotus-manage",
            path="src/core/outcomes/handoffs.py",
            reference_type=WorkflowPackDefinitionReferenceType.CONTRACT,
            required_for_registration=True,
            description="Manage-owned DpmOutcomeAiEvidenceInput contract that bounds AI-safe outcome-review evidence.",
        ),
        _definition_ref(
            reference_id="owner_service",
            repository="lotus-manage",
            path="src/api/services/outcome_review_service.py",
            reference_type=WorkflowPackDefinitionReferenceType.SERVICE,
            required_for_registration=True,
            description="Manage service that materializes immutable outcome reviews and AI evidence input without generating AI narrative locally.",
        ),
        _definition_ref(
            reference_id="owner_router",
            repository="lotus-manage",
            path="src/api/routers/outcome_reviews.py",
            reference_type=WorkflowPackDefinitionReferenceType.ROUTER,
            required_for_registration=True,
            description="Manage API route exposing bounded outcome-review AI evidence input.",
        ),
        _definition_ref(
            reference_id="owner_tests",
            repository="lotus-manage",
            path="tests/unit/core/test_outcome_handoffs.py",
            reference_type=WorkflowPackDefinitionReferenceType.TEST,
            required_for_registration=True,
            description="Manage regression coverage proving forbidden fields and actions are removed from outcome AI evidence.",
        ),
        _definition_ref(
            reference_id="owner_rfc",
            repository="lotus-manage",
            path="docs/rfcs/RFC-0042-post-trade-outcome-feedback-loop.md",
            reference_type=WorkflowPackDefinitionReferenceType.RFC,
            required_for_registration=False,
            description="RFC-0042 defines the post-trade outcome evidence boundary and excludes PM scoring, autonomous execution, and client contact.",
        ),
    ]


def _dpm_wave_pm_memo_v1_definition_refs() -> list[WorkflowPackDefinitionReferenceDescriptor]:
    return [
        _definition_ref(
            reference_id="primary_contract",
            repository="lotus-manage",
            path="src/core/waves/handoffs.py",
            reference_type=WorkflowPackDefinitionReferenceType.CONTRACT,
            required_for_registration=True,
            description="Manage-owned DpmWaveReportInput contract that bounds rebalance-wave evidence for PM memo drafting.",
        ),
        _definition_ref(
            reference_id="owner_service",
            repository="lotus-manage",
            path="src/api/services/wave_service.py",
            reference_type=WorkflowPackDefinitionReferenceType.SERVICE,
            required_for_registration=True,
            description="Manage service that materializes governed rebalance waves and deterministic report input without generating AI narrative locally.",
        ),
        _definition_ref(
            reference_id="owner_router",
            repository="lotus-manage",
            path="src/api/routers/waves.py",
            reference_type=WorkflowPackDefinitionReferenceType.ROUTER,
            required_for_registration=True,
            description="Manage API route exposing bounded rebalance-wave report input for downstream report, archive, and AI execution.",
        ),
        _definition_ref(
            reference_id="owner_tests",
            repository="lotus-manage",
            path="tests/unit/dpm/api/test_waves_api.py",
            reference_type=WorkflowPackDefinitionReferenceType.TEST,
            required_for_registration=True,
            description="Manage regression coverage proving wave report input remains bounded, source-linked, and workflow safe.",
        ),
        _definition_ref(
            reference_id="owner_rfc",
            repository="lotus-manage",
            path="docs/rfcs/RFC-0041-rebalance-wave-orchestration-and-cio-model-change-impact.md",
            reference_type=WorkflowPackDefinitionReferenceType.RFC,
            required_for_registration=False,
            description="RFC-0041 defines rebalance-wave orchestration, CIO impact review, and no-autonomous-execution workflow boundaries.",
        ),
    ]


def _dpm_operations_handoff_summary_v1_definition_refs() -> list[
    WorkflowPackDefinitionReferenceDescriptor
]:
    return [
        _definition_ref(
            reference_id="primary_contract",
            repository="lotus-manage",
            path="src/core/waves/handoffs.py",
            reference_type=WorkflowPackDefinitionReferenceType.CONTRACT,
            required_for_registration=True,
            description=(
                "Manage-owned DpmWaveReportInput contract that bounds internal operations "
                "handoff evidence for summary drafting."
            ),
        ),
        _definition_ref(
            reference_id="owner_service",
            repository="lotus-manage",
            path="src/api/services/wave_service.py",
            reference_type=WorkflowPackDefinitionReferenceType.SERVICE,
            required_for_registration=True,
            description=(
                "Manage service that materializes governed rebalance waves, staged item posture, "
                "and internal handoff refs without generating AI narrative locally."
            ),
        ),
        _definition_ref(
            reference_id="owner_router",
            repository="lotus-manage",
            path="src/api/routers/waves.py",
            reference_type=WorkflowPackDefinitionReferenceType.ROUTER,
            required_for_registration=True,
            description=(
                "Manage API route exposing bounded rebalance-wave report input and internal "
                "operations handoff evidence for downstream AI execution."
            ),
        ),
        _definition_ref(
            reference_id="owner_tests",
            repository="lotus-manage",
            path="tests/unit/dpm/api/test_waves_api.py",
            reference_type=WorkflowPackDefinitionReferenceType.TEST,
            required_for_registration=True,
            description=(
                "Manage regression coverage proving wave report and handoff input remains "
                "bounded, source-linked, and does not claim external execution."
            ),
        ),
        _definition_ref(
            reference_id="owner_rfc",
            repository="lotus-manage",
            path="docs/rfcs/RFC-0043-governed-ai-pm-copilot-for-dpm.md",
            reference_type=WorkflowPackDefinitionReferenceType.RFC,
            required_for_registration=False,
            description=(
                "RFC-0043 defines governed operations handoff summary support, no-domain-decision "
                "guardrails, review posture, and unavailable behavior."
            ),
        ),
    ]


def _dpm_exception_summary_v1_definition_refs() -> list[WorkflowPackDefinitionReferenceDescriptor]:
    return [
        _definition_ref(
            reference_id="primary_contract",
            repository="lotus-manage",
            path="src/core/mandates.py",
            reference_type=WorkflowPackDefinitionReferenceType.CONTRACT,
            required_for_registration=True,
            description=(
                "Manage-owned monitoring exception models that bound exception identity, severity, "
                "state, reason code, recommended action, and source lineage."
            ),
        ),
        _definition_ref(
            reference_id="owner_service",
            repository="lotus-manage",
            path="src/api/services/monitoring_service.py",
            reference_type=WorkflowPackDefinitionReferenceType.SERVICE,
            required_for_registration=True,
            description=(
                "Manage service that materializes mandate monitoring runs and exception posture "
                "without generating AI narrative locally."
            ),
        ),
        _definition_ref(
            reference_id="owner_router",
            repository="lotus-manage",
            path="src/api/routers/monitoring.py",
            reference_type=WorkflowPackDefinitionReferenceType.ROUTER,
            required_for_registration=True,
            description=(
                "Manage API route exposing bounded mandate monitoring exception evidence for "
                "downstream AI support summaries."
            ),
        ),
        _definition_ref(
            reference_id="owner_tests",
            repository="lotus-manage",
            path="tests/unit/dpm/api/test_monitoring_api.py",
            reference_type=WorkflowPackDefinitionReferenceType.TEST,
            required_for_registration=True,
            description=(
                "Manage regression coverage proving monitoring exceptions remain source-linked, "
                "bounded, and review-oriented."
            ),
        ),
        _definition_ref(
            reference_id="owner_rfc",
            repository="lotus-manage",
            path="docs/rfcs/RFC-0043-governed-ai-pm-copilot-for-dpm.md",
            reference_type=WorkflowPackDefinitionReferenceType.RFC,
            required_for_registration=False,
            description=(
                "RFC-0043 defines governed exception-summary support, no-domain-decision "
                "guardrails, review posture, and unavailable behavior."
            ),
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
