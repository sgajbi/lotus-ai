from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.contracts.app_capability_rollouts import (
    AppCapabilityRolloutCatalogResponse,
    AppCapabilityRolloutDescriptor,
    AppCapabilityRolloutDetailResponse,
    AppCapabilityOnboardingTemplateResponse,
    AppCapabilityRolloutGovernanceItem,
    AppCapabilityRolloutGovernanceStatusResponse,
    AppCapabilityRolloutCatalogGovernanceStatusResponse,
    AppCapabilityRolloutGovernanceSummaryItem,
    AppCapabilityEscalationItem,
    AppCapabilityOwnershipBoundary,
    AppCapabilityRolloutStage,
    AppCapabilityRolloutTransitionDescriptor,
)
from app.contracts.capability_packs import (
    CapabilityPackAdoptionChecklistItem,
    CapabilityPackAdoptionCriterion,
    CapabilityPackCatalogResponse,
)
from app.contracts.production_go_live import ProductionGoLiveUseCaseApprovalResponse
from app.contracts.use_cases import (
    FirstUseCaseGovernanceStatusResponse,
    FirstUseCaseRuntimeStatusResponse,
)
from app.services.capability_pack_catalog import (
    build_capability_pack_catalog,
    get_capability_pack_by_id,
)
from app.services.capability_pack_adoption_template import build_capability_pack_adoption_template
from app.services.first_use_case_governance import build_first_use_case_governance_status
from app.services.first_use_case_status import build_first_use_case_runtime_status
from app.services.production_go_live_use_case_approval import (
    build_production_go_live_use_case_approval,
)
from app.services.use_case_onboarding_template import build_use_case_onboarding_template


@dataclass(frozen=True)
class AppCapabilityRolloutBuildContext:
    rollout_records: list[AppCapabilityRolloutDescriptor]


def build_app_capability_rollout_context(
    app_state: object | None = None,
    *,
    capability_catalog: CapabilityPackCatalogResponse | None = None,
    first_use_case: FirstUseCaseRuntimeStatusResponse | None = None,
    first_use_case_governance: FirstUseCaseGovernanceStatusResponse | None = None,
    production_go_live: ProductionGoLiveUseCaseApprovalResponse | None = None,
) -> AppCapabilityRolloutBuildContext:
    return AppCapabilityRolloutBuildContext(
        rollout_records=_build_rollout_records(
            app_state,
            capability_catalog=capability_catalog,
            first_use_case=first_use_case,
            first_use_case_governance=first_use_case_governance,
            production_go_live=production_go_live,
        )
    )


def build_app_capability_rollout_catalog(
    app_state: object | None = None,
    *,
    context: AppCapabilityRolloutBuildContext | None = None,
) -> AppCapabilityRolloutCatalogResponse:
    rollout_records = _resolve_rollout_context(app_state, context).rollout_records
    onboarded_pairing_count = sum(1 for record in rollout_records if record.currently_onboarded)
    active_pairing_count = sum(
        1
        for record in rollout_records
        if record.rollout_stage
        in {
            AppCapabilityRolloutStage.LIMITED_ROLLOUT,
            AppCapabilityRolloutStage.ACTIVE_PRODUCTION,
        }
    )
    downstream_app_count = len({record.downstream_app for record in rollout_records})
    return AppCapabilityRolloutCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        phase=settings.delivery_phase,
        pairing_count=len(rollout_records),
        onboarded_pairing_count=onboarded_pairing_count,
        active_pairing_count=active_pairing_count,
        downstream_app_count=downstream_app_count,
        rollout_records=rollout_records,
        status_summary=[
            "App-capability rollout records are now modeled separately from global capability-pack maturity so downstream rollout truth stays pairing-specific.",
            "Slice 1 is intentionally catalog-first: it exposes status and rollout-stage truth without yet introducing ownership, pause, rollback, or retirement controls.",
            "The first implemented lotus-performance pairing remains the concrete anchor while later candidate apps stay visible as not-onboarded rollout records instead of living only in RFC prose.",
        ],
    )


def build_app_capability_onboarding_template(
    *, downstream_app: str, capability_pack_id: str, app_state: object | None = None
) -> AppCapabilityOnboardingTemplateResponse:
    record = get_app_capability_rollout_record(
        downstream_app=downstream_app,
        capability_pack_id=capability_pack_id,
        app_state=app_state,
    )
    pack_template = build_capability_pack_adoption_template(capability_pack_id)
    reference_use_case_template = (
        build_use_case_onboarding_template()
        if record.current_anchor_use_case_id == "lotus_performance.analytics_commentary.v1"
        else None
    )
    checklist = list(pack_template.checklist)
    if reference_use_case_template is not None:
        checklist.extend(
            CapabilityPackAdoptionChecklistItem(
                checklist_id=item.checklist_id,
                phase=item.phase,
                required=item.required,
                notes=item.notes,
            )
            for item in reference_use_case_template.checklist
            if item.checklist_id
            in {
                "runtime_eval_family_staged_and_passing",
                "limited_rollout_support_path_reviewed",
                "observability_and_artifact_review_path_available",
            }
        )
    approval_criteria = list(pack_template.approval_criteria)
    if reference_use_case_template is not None:
        approval_criteria.extend(
            CapabilityPackAdoptionCriterion(
                criterion_id=criterion.criterion_id,
                criterion_name=criterion.criterion_name,
                evaluation_surface=criterion.evaluation_surface,
                pass_condition=criterion.pass_condition,
            )
            for criterion in reference_use_case_template.approval_criteria
            if criterion.criterion_id
            in {
                "approval_runtime_readiness",
                "approval_runbook_readiness",
                "approval_governance_summary",
            }
        )
    return AppCapabilityOnboardingTemplateResponse(
        service=settings.service_name,
        version=settings.service_version,
        template_id=f"{downstream_app}.{capability_pack_id}.onboarding-template.v1",
        downstream_app=downstream_app,
        capability_pack_id=capability_pack_id,
        current_rollout_stage=record.rollout_stage,
        based_on_pack_template_id=pack_template.template_id,
        reference_use_case_template_id=(
            reference_use_case_template.template_id
            if reference_use_case_template is not None
            else None
        ),
        checklist=checklist,
        approval_criteria=approval_criteria,
        status_summary=[
            "App-capability onboarding now composes reusable pack adoption guidance with pairing-specific rollout truth instead of rebuilding onboarding from scratch for each app.",
            (
                "The current pairing reuses the first implemented use-case onboarding template as an active reference."
                if reference_use_case_template is not None
                else "The current pairing reuses the pack-native adoption template only, because no direct implemented reference use-case template applies yet."
            ),
        ],
    )


def build_app_capability_rollout_detail(
    *,
    downstream_app: str,
    capability_pack_id: str,
    app_state: object | None = None,
    context: AppCapabilityRolloutBuildContext | None = None,
) -> AppCapabilityRolloutDetailResponse:
    record = get_app_capability_rollout_record(
        downstream_app=downstream_app,
        capability_pack_id=capability_pack_id,
        app_state=app_state,
        context=context,
    )
    return _build_rollout_detail_response(record=record)


def _build_rollout_detail_response(
    *, record: AppCapabilityRolloutDescriptor
) -> AppCapabilityRolloutDetailResponse:
    ownership_boundaries = _build_ownership_boundaries(record=record)
    escalation_paths = _build_escalation_paths(record=record)
    transition_targets = _build_transition_targets(record=record)
    return AppCapabilityRolloutDetailResponse(
        service=settings.service_name,
        version=settings.service_version,
        record=record,
        ownership_boundaries=ownership_boundaries,
        escalation_paths=escalation_paths,
        transition_targets=transition_targets,
        status_summary=[
            "App-capability rollout detail now exposes ownership, escalation, and lifecycle-transition posture per pairing.",
            (
                "The pairing remains below rollout-governed traffic until both explicit ownership and bounded transition posture are in place."
                if record.rollout_stage
                in {
                    AppCapabilityRolloutStage.NOT_ONBOARDED,
                    AppCapabilityRolloutStage.INTEGRATION_IN_PROGRESS,
                }
                else "The pairing now has a non-preparatory rollout stage and must retain explicit support, escalation, and transition posture."
            ),
        ],
    )


def build_app_capability_rollout_governance_status(
    *,
    downstream_app: str,
    capability_pack_id: str,
    app_state: object | None = None,
    context: AppCapabilityRolloutBuildContext | None = None,
) -> AppCapabilityRolloutGovernanceStatusResponse:
    detail = build_app_capability_rollout_detail(
        downstream_app=downstream_app,
        capability_pack_id=capability_pack_id,
        app_state=app_state,
        context=context,
    )
    return _build_governance_status_response(detail=detail)


def _build_governance_status_response(
    *, detail: AppCapabilityRolloutDetailResponse
) -> AppCapabilityRolloutGovernanceStatusResponse:
    items = _build_governance_items(detail=detail)
    blocking_area_count = sum(
        1 for item in items if item.required_for_rollout and item.status != "READY"
    )
    governance_ready = blocking_area_count == 0
    return AppCapabilityRolloutGovernanceStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        record=detail.record,
        governance_ready=governance_ready,
        blocking_area_count=blocking_area_count,
        ownership_boundaries=detail.ownership_boundaries,
        escalation_paths=detail.escalation_paths,
        transition_targets=detail.transition_targets,
        items=items,
        status_summary=[
            (
                "The app-capability pairing currently satisfies bounded ownership and rollout governance posture."
                if governance_ready
                else "The app-capability pairing remains blocked in governance review until ownership, escalation, and rollout transition posture are all explicit."
            ),
            (
                "Pause, rollback, and retirement are now modeled as first-class rollout transitions even when the current pairing is not using them."
            ),
        ],
    )


def build_app_capability_rollout_catalog_governance_status(
    app_state: object | None = None,
    *,
    context: AppCapabilityRolloutBuildContext | None = None,
) -> AppCapabilityRolloutCatalogGovernanceStatusResponse:
    rollout_context = _resolve_rollout_context(app_state, context)
    summaries: list[AppCapabilityRolloutGovernanceSummaryItem] = []
    ready_pairing_count = 0
    for record in rollout_context.rollout_records:
        governance = _build_governance_status_response(
            detail=_build_rollout_detail_response(record=record)
        )
        if governance.governance_ready:
            ready_pairing_count += 1
        summaries.append(
            AppCapabilityRolloutGovernanceSummaryItem(
                downstream_app=record.downstream_app,
                capability_pack_id=record.capability_pack_id,
                governance_ready=governance.governance_ready,
                rollout_stage=record.rollout_stage,
                blocking_area_count=governance.blocking_area_count,
            )
        )
    blocking_pairing_count = len(summaries) - ready_pairing_count
    return AppCapabilityRolloutCatalogGovernanceStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        governance_ready=blocking_pairing_count == 0,
        ready_pairing_count=ready_pairing_count,
        blocking_pairing_count=blocking_pairing_count,
        pairing_summaries=summaries,
        status_summary=[
            (
                "All currently modeled app-capability pairings satisfy bounded ownership and rollout governance posture."
                if blocking_pairing_count == 0
                else f"{blocking_pairing_count} currently modeled app-capability pairing(s) remain blocked in governance review."
            )
        ],
    )


def get_app_capability_rollout_record(
    *,
    downstream_app: str,
    capability_pack_id: str,
    app_state: object | None = None,
    context: AppCapabilityRolloutBuildContext | None = None,
) -> AppCapabilityRolloutDescriptor:
    for record in _resolve_rollout_context(app_state, context).rollout_records:
        if (
            record.downstream_app == downstream_app
            and record.capability_pack_id == capability_pack_id
        ):
            return record
    raise ValueError(f"Unknown app-capability rollout: {downstream_app} / {capability_pack_id}")


def _resolve_rollout_context(
    app_state: object | None,
    context: AppCapabilityRolloutBuildContext | None,
) -> AppCapabilityRolloutBuildContext:
    return context if context is not None else build_app_capability_rollout_context(app_state)


def _build_rollout_records(
    app_state: object | None,
    *,
    capability_catalog: CapabilityPackCatalogResponse | None = None,
    first_use_case: FirstUseCaseRuntimeStatusResponse | None = None,
    first_use_case_governance: FirstUseCaseGovernanceStatusResponse | None = None,
    production_go_live: ProductionGoLiveUseCaseApprovalResponse | None = None,
) -> list[AppCapabilityRolloutDescriptor]:
    capability_catalog = (
        capability_catalog if capability_catalog is not None else build_capability_pack_catalog()
    )
    pack_by_id = {pack.pack_id: pack for pack in capability_catalog.packs}
    first_use_case = (
        first_use_case if first_use_case is not None else build_first_use_case_runtime_status()
    )
    first_use_case_governance = (
        first_use_case_governance
        if first_use_case_governance is not None
        else build_first_use_case_governance_status()
    )
    production_go_live = (
        production_go_live
        if production_go_live is not None
        else build_production_go_live_use_case_approval(app_state)
    )

    analytics_pack = pack_by_id["analytics_commentary.pack.v1"]
    decision_pack = pack_by_id["decision_explanation.pack.v1"]

    lotus_performance_stage = _resolve_lotus_performance_rollout_stage(
        limited_rollout_ready=first_use_case_governance.governance_ready,
        active_production_ready=production_go_live.active_production_ready,
    )

    return [
        AppCapabilityRolloutDescriptor(
            downstream_app=first_use_case.downstream_app,
            capability_pack_id=analytics_pack.pack_id,
            capability_pack_family_id=analytics_pack.family_id,
            capability_pack_maturity_stage=analytics_pack.maturity_stage,
            rollout_stage=lotus_performance_stage,
            currently_onboarded=True,
            current_anchor_use_case_id=first_use_case.use_case_id,
            rollout_review_surface="/platform/use-cases/first-production-use-case/governance-status",
            status_summary=[
                "Lotus-performance is the current implemented app-capability anchor for analytics commentary.",
                (
                    "The pairing is ready for bounded limited rollout."
                    if lotus_performance_stage is AppCapabilityRolloutStage.LIMITED_ROLLOUT
                    else "The pairing is still below limited-rollout approval, so it remains in governed integration posture."
                ),
            ],
        ),
        _build_not_onboarded_record(
            downstream_app="lotus-manage",
            pack_id=analytics_pack.pack_id,
            rollout_review_surface=f"/platform/capability-packs/{analytics_pack.pack_id}/adoption-template",
            summary=(
                "Lotus-manage is a likely next analytics-commentary candidate, but no governed pairing record beyond not-onboarded posture exists yet."
            ),
        ),
        _build_not_onboarded_record(
            downstream_app="lotus-risk",
            pack_id=analytics_pack.pack_id,
            rollout_review_surface=f"/platform/capability-packs/{analytics_pack.pack_id}/adoption-template",
            summary=(
                "Lotus-risk is visible as a future commentary-pack adoption target without implying that integration work has started."
            ),
        ),
        _build_not_onboarded_record(
            downstream_app="lotus-advise",
            pack_id=decision_pack.pack_id,
            rollout_review_surface=f"/platform/capability-packs/{decision_pack.pack_id}/adoption-template",
            summary=(
                "Lotus-advise is visible as a future decision-explanation-pack adoption target while the pack itself remains experimental."
            ),
        ),
    ]


def _build_not_onboarded_record(
    *,
    downstream_app: str,
    pack_id: str,
    rollout_review_surface: str,
    summary: str,
) -> AppCapabilityRolloutDescriptor:
    pack = get_capability_pack_by_id(pack_id)
    if pack is None:
        raise RuntimeError(f"{pack_id} capability pack is not registered")
    return AppCapabilityRolloutDescriptor(
        downstream_app=downstream_app,
        capability_pack_id=pack.pack_id,
        capability_pack_family_id=pack.family_id,
        capability_pack_maturity_stage=pack.maturity_stage,
        rollout_stage=AppCapabilityRolloutStage.NOT_ONBOARDED,
        currently_onboarded=False,
        current_anchor_use_case_id=None,
        rollout_review_surface=rollout_review_surface,
        status_summary=[
            summary,
            "Global pack maturity remains visible here, but this app-specific rollout record is still not onboarded.",
        ],
    )


def _resolve_lotus_performance_rollout_stage(
    *, limited_rollout_ready: bool, active_production_ready: bool
) -> AppCapabilityRolloutStage:
    if active_production_ready:
        return AppCapabilityRolloutStage.ACTIVE_PRODUCTION
    if limited_rollout_ready:
        return AppCapabilityRolloutStage.LIMITED_ROLLOUT
    return AppCapabilityRolloutStage.INTEGRATION_IN_PROGRESS


def _build_ownership_boundaries(
    *, record: AppCapabilityRolloutDescriptor
) -> list[AppCapabilityOwnershipBoundary]:
    if record.downstream_app == "lotus-performance":
        return [
            AppCapabilityOwnershipBoundary(
                owner="lotus-ai",
                responsibility="pack_runtime_and_governance",
                notes="Lotus-ai owns the capability-pack runtime, quality-gate, provider, safety, and audit posture for the pairing.",
            ),
            AppCapabilityOwnershipBoundary(
                owner="lotus-performance",
                responsibility="domain_fact_computation_and_user_delivery",
                notes="Lotus-performance owns deterministic analytics computation, caller shaping, and final user-facing product delivery.",
            ),
            AppCapabilityOwnershipBoundary(
                owner="shared",
                responsibility="limited_rollout_support_and_rollback_review",
                notes="Lotus-ai and lotus-performance share rollout review, support triage, and rollback decisions for this bounded pairing.",
            ),
        ]
    return [
        AppCapabilityOwnershipBoundary(
            owner="lotus-ai",
            responsibility="pack_adoption_template_and_platform_review",
            notes="Lotus-ai currently owns the reusable pack contract and the pre-onboarding governance model for this pairing.",
        ),
        AppCapabilityOwnershipBoundary(
            owner=record.downstream_app,
            responsibility="downstream_integration_owner_tbd",
            notes="The downstream app is identified as the future integration owner, but named implementation ownership is not yet established.",
        ),
    ]


def _build_escalation_paths(
    *, record: AppCapabilityRolloutDescriptor
) -> list[AppCapabilityEscalationItem]:
    if record.downstream_app == "lotus-performance":
        return [
            AppCapabilityEscalationItem(
                escalation_id="shared_rollout_review",
                status="READY",
                notes="Shared rollout review is already documented through the first-use-case support and governance surfaces.",
            ),
            AppCapabilityEscalationItem(
                escalation_id="active_production_escalation",
                status="NOT_READY",
                notes="The pairing is not yet approved for active production, so broader incident and escalation posture remains below full ready state.",
            ),
        ]
    return [
        AppCapabilityEscalationItem(
            escalation_id="integration_owner_assignment",
            status="NOT_READY",
            notes="Named downstream escalation remains unset until the app-capability pairing moves beyond not-onboarded posture.",
        )
    ]


def _build_transition_targets(
    *, record: AppCapabilityRolloutDescriptor
) -> list[AppCapabilityRolloutTransitionDescriptor]:
    stage = record.rollout_stage
    if stage is AppCapabilityRolloutStage.NOT_ONBOARDED:
        return [
            AppCapabilityRolloutTransitionDescriptor(
                target_stage=AppCapabilityRolloutStage.INTEGRATION_IN_PROGRESS,
                allowed_now=True,
                notes="The first supported transition for a not-onboarded pairing is explicit integration work.",
            ),
            AppCapabilityRolloutTransitionDescriptor(
                target_stage=AppCapabilityRolloutStage.RETIRED,
                allowed_now=True,
                notes="A stale not-onboarded pairing may be retired explicitly instead of lingering indefinitely in the catalog.",
            ),
        ]
    if stage is AppCapabilityRolloutStage.INTEGRATION_IN_PROGRESS:
        return [
            AppCapabilityRolloutTransitionDescriptor(
                target_stage=AppCapabilityRolloutStage.LIMITED_ROLLOUT,
                allowed_now=record.downstream_app == "lotus-performance",
                notes=(
                    "The current implemented pairing may later graduate to limited rollout once its existing first-use-case governance path is ready."
                    if record.downstream_app == "lotus-performance"
                    else "Later candidate pairings cannot move to limited rollout until named ownership and downstream integration governance are established."
                ),
            ),
            AppCapabilityRolloutTransitionDescriptor(
                target_stage=AppCapabilityRolloutStage.PAUSED_OR_ROLLED_BACK,
                allowed_now=True,
                notes="Integration work can be paused or rolled back explicitly without deleting the pairing record.",
            ),
            AppCapabilityRolloutTransitionDescriptor(
                target_stage=AppCapabilityRolloutStage.RETIRED,
                allowed_now=True,
                notes="An integration-stage pairing may be retired explicitly when the downstream app or shared platform no longer intends to pursue the adoption path.",
            ),
        ]
    if stage is AppCapabilityRolloutStage.LIMITED_ROLLOUT:
        return [
            AppCapabilityRolloutTransitionDescriptor(
                target_stage=AppCapabilityRolloutStage.ACTIVE_PRODUCTION,
                allowed_now=False,
                notes="Active production remains a later approval boundary beyond this slice.",
            ),
            AppCapabilityRolloutTransitionDescriptor(
                target_stage=AppCapabilityRolloutStage.PAUSED_OR_ROLLED_BACK,
                allowed_now=True,
                notes="Rollback from limited rollout is a first-class lifecycle transition.",
            ),
            AppCapabilityRolloutTransitionDescriptor(
                target_stage=AppCapabilityRolloutStage.RETIRED,
                allowed_now=True,
                notes="Retirement is modeled explicitly so stale pairings do not have to linger indefinitely.",
            ),
        ]
    if stage is AppCapabilityRolloutStage.ACTIVE_PRODUCTION:
        return [
            AppCapabilityRolloutTransitionDescriptor(
                target_stage=AppCapabilityRolloutStage.PAUSED_OR_ROLLED_BACK,
                allowed_now=True,
                notes="Pause or rollback remains the first supported withdrawal target for an active pairing.",
            ),
            AppCapabilityRolloutTransitionDescriptor(
                target_stage=AppCapabilityRolloutStage.RETIRED,
                allowed_now=True,
                notes="Retirement remains a separate lifecycle decision from rollback.",
            ),
        ]
    if stage is AppCapabilityRolloutStage.PAUSED_OR_ROLLED_BACK:
        return [
            AppCapabilityRolloutTransitionDescriptor(
                target_stage=AppCapabilityRolloutStage.INTEGRATION_IN_PROGRESS,
                allowed_now=True,
                notes="A paused pairing may return to explicit integration posture before any later rollout recovery.",
            ),
            AppCapabilityRolloutTransitionDescriptor(
                target_stage=AppCapabilityRolloutStage.RETIRED,
                allowed_now=True,
                notes="A paused pairing may be retired explicitly instead of resumed.",
            ),
        ]
    return []


def _build_governance_items(
    *, detail: AppCapabilityRolloutDetailResponse
) -> list[AppCapabilityRolloutGovernanceItem]:
    named_downstream_owner_ready = any(
        boundary.owner == detail.record.downstream_app and "tbd" not in boundary.responsibility
        for boundary in detail.ownership_boundaries
    )
    shared_support_ready = any(path.status == "READY" for path in detail.escalation_paths)
    lifecycle_modeled = any(
        transition.target_stage
        in {
            AppCapabilityRolloutStage.PAUSED_OR_ROLLED_BACK,
            AppCapabilityRolloutStage.RETIRED,
        }
        for transition in detail.transition_targets
    )
    return [
        AppCapabilityRolloutGovernanceItem(
            item_id="platform_ownership_boundary",
            status="READY",
            required_for_rollout=True,
            notes="Lotus-ai platform ownership is explicit for every modeled app-capability pairing.",
        ),
        AppCapabilityRolloutGovernanceItem(
            item_id="downstream_owner_boundary",
            status="READY" if named_downstream_owner_ready else "NOT_READY",
            required_for_rollout=True,
            notes="Named downstream integration ownership must be explicit before the pairing can be treated as rollout-governed.",
        ),
        AppCapabilityRolloutGovernanceItem(
            item_id="support_and_escalation_path",
            status="READY" if shared_support_ready else "NOT_READY",
            required_for_rollout=True,
            notes="Support and escalation must be explicit so rollout incidents do not become ambiguous between lotus-ai and the downstream app.",
        ),
        AppCapabilityRolloutGovernanceItem(
            item_id="pause_rollback_retirement_model",
            status="READY" if lifecycle_modeled else "NOT_READY",
            required_for_rollout=True,
            notes="Pause, rollback, and retirement must remain modeled as first-class lifecycle transitions per pairing.",
        ),
    ]
