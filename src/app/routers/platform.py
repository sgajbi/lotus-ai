from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.contracts.governed_actions import (
    GovernedActionHistoryResponse,
    GovernedActionStatus,
)
from app.http.authenticated_caller import AuthenticatedCallerDependency
from app.services.governed_action_control import build_governed_action_history

from app.contracts.app_capability_rollouts import (
    AppCapabilityRolloutCatalogGovernanceStatusResponse,
    AppCapabilityRolloutCatalogLifecycleStatusResponse,
    AppCapabilityRolloutCatalogResponse,
    AppCapabilityRolloutDetailResponse,
    AppCapabilityRolloutGovernanceStatusResponse,
    AppCapabilityRolloutLifecycleStatusResponse,
    AppCapabilityOnboardingTemplateResponse,
    AppCapabilityRolloutObservabilitySummaryResponse,
)
from app.contracts.deployment_split import (
    DeploymentSplitActivationReadinessResponse,
    DeploymentSplitGovernanceStatusResponse,
    DeploymentSplitRunbookReadinessResponse,
    DeploymentSplitRuntimeStatusResponse,
)
from app.contracts.platform import PlatformRuntimeStatusResponse
from app.contracts.production_baseline import (
    ProductionBaselineActivationReadinessResponse,
    ProductionBaselineGovernanceStatusResponse,
    ProductionBaselineRunbookReadinessResponse,
    ProductionBaselineRuntimeStatusResponse,
)
from app.contracts.production_go_live import ProductionGoLiveRuntimeStatusResponse
from app.contracts.production_go_live import (
    ProductionGoLiveActivationReadinessResponse,
    ProductionGoLiveGovernanceStatusResponse,
    ProductionGoLiveRunbookReadinessResponse,
    ProductionGoLiveUseCaseApprovalResponse,
)
from app.contracts.resilience import (
    ResilienceActivationReadinessResponse,
    ResilienceDrillEvidenceResponse,
    ResilienceGovernanceStatusResponse,
    ResilienceRestorePlanResponse,
    ResilienceRunbookReadinessResponse,
    ResilienceRuntimeStatusResponse,
)
from app.services.production_baseline_activation_readiness import (
    build_production_baseline_activation_readiness,
)
from app.services.app_capability_rollout_catalog import (
    build_app_capability_rollout_catalog,
    build_app_capability_rollout_catalog_governance_status,
    build_app_capability_rollout_detail,
    build_app_capability_rollout_governance_status,
    build_app_capability_onboarding_template,
)
from app.services.app_capability_rollout_lifecycle import (
    build_app_capability_rollout_catalog_lifecycle_status,
    build_app_capability_rollout_lifecycle_status,
)
from app.services.app_capability_rollout_observability import (
    build_app_capability_rollout_observability_summary,
)
from app.services.production_baseline_governance import (
    build_production_baseline_governance_status,
)
from app.services.readiness_catalog import (
    build_production_baseline_runbook_readiness,
)
from app.services.deployment_split_activation_readiness import (
    build_deployment_split_activation_readiness,
)
from app.services.deployment_split_governance import build_deployment_split_governance_status
from app.services.readiness_catalog import (
    build_deployment_split_runbook_readiness,
)
from app.services.platform_status import build_platform_runtime_status
from app.services.deployment_split_runtime import build_deployment_split_runtime_status
from app.services.production_baseline_runtime import build_production_baseline_runtime_status
from app.services.production_go_live_activation_readiness import (
    build_production_go_live_activation_readiness,
)
from app.services.production_go_live_governance import build_production_go_live_governance_status
from app.services.production_go_live_runbook_readiness import (
    build_production_go_live_runbook_readiness,
)
from app.services.production_go_live_use_case_approval import (
    build_production_go_live_use_case_approval,
)
from app.services.production_go_live_runtime import build_production_go_live_runtime_status
from app.services.resilience_activation_readiness import build_resilience_activation_readiness
from app.services.resilience_drill_evidence import build_resilience_drill_evidence
from app.services.resilience_governance import build_resilience_governance_status
from app.services.resilience_restore_plan import build_resilience_restore_plan
from app.services.readiness_catalog import build_resilience_runbook_readiness
from app.services.resilience_runtime import build_resilience_runtime_status

router = APIRouter(prefix="/platform", tags=["platform"])


@router.get(
    "/runtime-status",
    response_model=PlatformRuntimeStatusResponse,
    operation_id="getPlatformRuntimeStatus",
    summary="Get lotus-ai platform runtime status",
    description=(
        "Returns the current lotus-ai operating posture across provider execution, safety, "
        "prompt registry, retrieval, and persistence modes."
    ),
    responses={
        200: {"description": "Platform runtime status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_platform_runtime_status_route(request: Request) -> PlatformRuntimeStatusResponse:
    return build_platform_runtime_status(request.app.state)


@router.get(
    "/governed-actions",
    response_model=GovernedActionHistoryResponse,
    operation_id="getGovernedActionHistory",
    summary="Get governed-action evidence records",
    description=(
        "Returns governed-action evidence records across every domain that composes the "
        "governed-action primitive (kill-switch clearance, prompt promotion, provider "
        "resets, model promotions, capability restores, system-originated recovery), "
        "newest requested first. This is the read the approval flow presupposes: an "
        "approver reviews the exact pending action - payload and hash - before approving "
        "it, and an auditor reconstructs the request-approval-execution chain, including "
        "evidence pinned only here such as a capability degradation cleared by an "
        "executed restore. Filterable by status and target. This is control-plane "
        "operator evidence: the read requires provider-control or prompt-control "
        "authorization, and denied and successful reads are both recorded on the "
        "privileged-access ledger."
    ),
    responses={
        200: {"description": "Governed-action records returned successfully."},
        403: {
            "description": "Caller holds no control-plane operator capability; the denial "
            "is recorded on the privileged-access ledger."
        },
        500: {"description": "Unexpected server error."},
    },
)
async def get_governed_action_history_route(
    authenticated_caller: AuthenticatedCallerDependency,
    status: GovernedActionStatus | None = None,
    target: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> GovernedActionHistoryResponse:
    return build_governed_action_history(
        authenticated_caller, status_filter=status, target=target, limit=limit
    )


@router.get(
    "/app-capability-rollouts",
    response_model=AppCapabilityRolloutCatalogResponse,
    operation_id="getAppCapabilityRolloutCatalog",
    summary="Get RFC-0023 app-capability rollout catalog",
    description=(
        "Returns the current RFC-0023 app-capability rollout records across downstream applications "
        "and capability packs, keeping global pack maturity distinct from app-specific rollout stage."
    ),
    responses={
        200: {"description": "App-capability rollout catalog returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_app_capability_rollout_catalog_route(
    request: Request,
) -> AppCapabilityRolloutCatalogResponse:
    return build_app_capability_rollout_catalog(request.app.state)


@router.get(
    "/app-capability-rollouts/governance-status",
    response_model=AppCapabilityRolloutCatalogGovernanceStatusResponse,
    operation_id="getAppCapabilityRolloutCatalogGovernanceStatus",
    summary="Get RFC-0023 app-capability rollout catalog governance status",
    description=(
        "Returns the current RFC-0023 catalog-level governance posture across downstream "
        "app-capability rollout pairings."
    ),
    responses={
        200: {
            "description": "App-capability rollout catalog governance status returned successfully."
        },
        500: {"description": "Unexpected server error."},
    },
)
async def get_app_capability_rollout_catalog_governance_status_route(
    request: Request,
) -> AppCapabilityRolloutCatalogGovernanceStatusResponse:
    return build_app_capability_rollout_catalog_governance_status(request.app.state)


@router.get(
    "/app-capability-rollouts/observability-summary",
    response_model=AppCapabilityRolloutObservabilitySummaryResponse,
    operation_id="getAppCapabilityRolloutObservabilitySummary",
    summary="Get RFC-0023 app-capability rollout observability summary",
    description=(
        "Returns the current RFC-0023 estate-wide rollout visibility posture across downstream "
        "app-capability pairings, including bounded activity samples and linked incident-review surfaces."
    ),
    responses={
        200: {"description": "App-capability rollout observability summary returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_app_capability_rollout_observability_summary_route(
    request: Request,
) -> AppCapabilityRolloutObservabilitySummaryResponse:
    return build_app_capability_rollout_observability_summary(request.app.state)


@router.get(
    "/app-capability-rollouts/lifecycle-status",
    response_model=AppCapabilityRolloutCatalogLifecycleStatusResponse,
    operation_id="getAppCapabilityRolloutCatalogLifecycleStatus",
    summary="Get RFC-0023 app-capability rollout lifecycle status",
    description=(
        "Returns the current RFC-0023 catalog-level lifecycle discipline posture across downstream "
        "app-capability rollout pairings, including retirement readiness and historical traceability."
    ),
    responses={
        200: {
            "description": "App-capability rollout catalog lifecycle status returned successfully."
        },
        500: {"description": "Unexpected server error."},
    },
)
async def get_app_capability_rollout_catalog_lifecycle_status_route(
    request: Request,
) -> AppCapabilityRolloutCatalogLifecycleStatusResponse:
    return build_app_capability_rollout_catalog_lifecycle_status(request.app.state)


@router.get(
    "/app-capability-rollouts/{downstream_app}/{capability_pack_id}",
    response_model=AppCapabilityRolloutDetailResponse,
    operation_id="getAppCapabilityRolloutDetail",
    summary="Get RFC-0023 app-capability rollout detail",
    description=(
        "Returns current rollout, ownership, escalation, and lifecycle-transition detail for one "
        "downstream app-capability pairing."
    ),
    responses={
        200: {"description": "App-capability rollout detail returned successfully."},
        404: {"description": "Unknown app-capability rollout pairing."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_app_capability_rollout_detail_route(
    downstream_app: str, capability_pack_id: str, request: Request
) -> AppCapabilityRolloutDetailResponse:
    try:
        return build_app_capability_rollout_detail(
            downstream_app=downstream_app,
            capability_pack_id=capability_pack_id,
            app_state=request.app.state,
        )
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/app-capability-rollouts/{downstream_app}/{capability_pack_id}/governance-status",
    response_model=AppCapabilityRolloutGovernanceStatusResponse,
    operation_id="getAppCapabilityRolloutGovernanceStatus",
    summary="Get RFC-0023 app-capability rollout governance status",
    description=(
        "Returns current ownership, escalation, and lifecycle governance posture for one "
        "downstream app-capability pairing."
    ),
    responses={
        200: {"description": "App-capability rollout governance status returned successfully."},
        404: {"description": "Unknown app-capability rollout pairing."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_app_capability_rollout_governance_status_route(
    downstream_app: str, capability_pack_id: str, request: Request
) -> AppCapabilityRolloutGovernanceStatusResponse:
    try:
        return build_app_capability_rollout_governance_status(
            downstream_app=downstream_app,
            capability_pack_id=capability_pack_id,
            app_state=request.app.state,
        )
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/app-capability-rollouts/{downstream_app}/{capability_pack_id}/lifecycle-status",
    response_model=AppCapabilityRolloutLifecycleStatusResponse,
    operation_id="getAppCapabilityRolloutLifecycleStatus",
    summary="Get RFC-0023 app-capability rollout lifecycle status",
    description=(
        "Returns current retirement readiness, lifecycle discipline, and historical traceability posture "
        "for one downstream app-capability pairing."
    ),
    responses={
        200: {"description": "App-capability rollout lifecycle status returned successfully."},
        404: {"description": "Unknown app-capability rollout pairing."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_app_capability_rollout_lifecycle_status_route(
    downstream_app: str, capability_pack_id: str, request: Request
) -> AppCapabilityRolloutLifecycleStatusResponse:
    try:
        return build_app_capability_rollout_lifecycle_status(
            downstream_app=downstream_app,
            capability_pack_id=capability_pack_id,
            app_state=request.app.state,
        )
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/app-capability-rollouts/{downstream_app}/{capability_pack_id}/onboarding-template",
    response_model=AppCapabilityOnboardingTemplateResponse,
    operation_id="getAppCapabilityOnboardingTemplate",
    summary="Get RFC-0023 app-capability onboarding template",
    description=(
        "Returns the reusable onboarding workflow and approval path for one downstream "
        "app-capability pairing."
    ),
    responses={
        200: {"description": "App-capability onboarding template returned successfully."},
        404: {"description": "Unknown app-capability rollout pairing."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_app_capability_onboarding_template_route(
    downstream_app: str, capability_pack_id: str, request: Request
) -> AppCapabilityOnboardingTemplateResponse:
    try:
        return build_app_capability_onboarding_template(
            downstream_app=downstream_app,
            capability_pack_id=capability_pack_id,
            app_state=request.app.state,
        )
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/resilience/runtime-status",
    response_model=ResilienceRuntimeStatusResponse,
    operation_id="getResilienceRuntimeStatus",
    summary="Get RFC-0017 resilience runtime status",
    description=(
        "Returns the current RFC-0017 resilience inventory across authoritative stores and "
        "critical runtime dependencies, including restart-survival and fallback posture."
    ),
    responses={
        200: {"description": "Resilience runtime status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_resilience_runtime_status_route() -> ResilienceRuntimeStatusResponse:
    return build_resilience_runtime_status()


@router.get(
    "/resilience/restore-plan",
    response_model=ResilienceRestorePlanResponse,
    operation_id="getResilienceRestorePlan",
    summary="Get RFC-0017 resilience restore plan",
    description=(
        "Returns the current bounded RFC-0017 restore ordering model across authoritative stores "
        "and critical dependencies, including validation criteria and rollback boundaries."
    ),
    responses={
        200: {"description": "Resilience restore plan returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_resilience_restore_plan_route() -> ResilienceRestorePlanResponse:
    return build_resilience_restore_plan()


@router.get(
    "/resilience/drill-evidence",
    response_model=ResilienceDrillEvidenceResponse,
    operation_id="getResilienceDrillEvidence",
    summary="Get RFC-0017 resilience drill evidence",
    description=(
        "Returns the current bounded resilience drill and recovery-proof evidence posture across "
        "authoritative stores and critical dependencies."
    ),
    responses={
        200: {"description": "Resilience drill evidence returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_resilience_drill_evidence_route() -> ResilienceDrillEvidenceResponse:
    return build_resilience_drill_evidence()


@router.get(
    "/resilience/activation-readiness",
    response_model=ResilienceActivationReadinessResponse,
    operation_id="getResilienceActivationReadiness",
    summary="Get RFC-0017 resilience activation readiness",
    description=(
        "Returns whether lotus-ai resilience posture is technically ready to be treated as an "
        "active governed capability rather than only an inventoried or ordered-recovery surface."
    ),
    responses={
        200: {"description": "Resilience activation readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_resilience_activation_readiness_route() -> ResilienceActivationReadinessResponse:
    return build_resilience_activation_readiness()


@router.get(
    "/resilience/runbook-readiness",
    response_model=ResilienceRunbookReadinessResponse,
    operation_id="getResilienceRunbookReadiness",
    summary="Get RFC-0017 resilience runbook readiness",
    description=(
        "Returns the current operator-runbook posture for restore ordering, queue and worker "
        "recovery, provider and retrieval recovery review, and drill boundaries."
    ),
    responses={
        200: {"description": "Resilience runbook readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_resilience_runbook_readiness_route() -> ResilienceRunbookReadinessResponse:
    return build_resilience_runbook_readiness()


@router.get(
    "/resilience/governance-status",
    response_model=ResilienceGovernanceStatusResponse,
    operation_id="getResilienceGovernanceStatus",
    summary="Get RFC-0017 resilience governance status",
    description=(
        "Returns the composed runtime, restore-plan, drill-evidence, activation-readiness, and "
        "runbook-readiness posture for the current RFC-0017 resilience rollout."
    ),
    responses={
        200: {"description": "Resilience governance status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_resilience_governance_status_route() -> ResilienceGovernanceStatusResponse:
    return build_resilience_governance_status()


@router.get(
    "/deployment-split/runtime-status",
    response_model=DeploymentSplitRuntimeStatusResponse,
    operation_id="getDeploymentSplitRuntimeStatus",
    summary="Get RFC-0015 deployment-split runtime status",
    description=(
        "Returns the current RFC-0015 deployment-split posture across runtime, retrieval, "
        "and eval planes, including configured versus effective stage and plane ownership."
    ),
    responses={
        200: {"description": "Deployment-split runtime status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_deployment_split_runtime_status_route(
    request: Request,
) -> DeploymentSplitRuntimeStatusResponse:
    return build_deployment_split_runtime_status(request.app.state)


@router.get(
    "/deployment-split/activation-readiness",
    response_model=DeploymentSplitActivationReadinessResponse,
    operation_id="getDeploymentSplitActivationReadiness",
    summary="Get RFC-0015 deployment-split activation readiness",
    description=(
        "Returns whether the configured RFC-0015 deployment-split stage is activatable without "
        "blocked or degraded split-plane posture."
    ),
    responses={
        200: {"description": "Deployment-split activation readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_deployment_split_activation_readiness_route(
    request: Request,
) -> DeploymentSplitActivationReadinessResponse:
    return build_deployment_split_activation_readiness(request.app.state)


@router.get(
    "/deployment-split/runbook-readiness",
    response_model=DeploymentSplitRunbookReadinessResponse,
    operation_id="getDeploymentSplitRunbookReadiness",
    summary="Get RFC-0015 deployment-split runbook readiness",
    description=(
        "Returns the current operator-runbook posture for unified, split-ready, retrieval-split, "
        "and retrieval-and-evals-split deployment stages."
    ),
    responses={
        200: {"description": "Deployment-split runbook readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_deployment_split_runbook_readiness_route() -> DeploymentSplitRunbookReadinessResponse:
    return build_deployment_split_runbook_readiness()


@router.get(
    "/deployment-split/governance-status",
    response_model=DeploymentSplitGovernanceStatusResponse,
    operation_id="getDeploymentSplitGovernanceStatus",
    summary="Get RFC-0015 deployment-split governance status",
    description=(
        "Returns the composed runtime, activation, runbook, and observability posture for the "
        "configured RFC-0015 deployment-split stage."
    ),
    responses={
        200: {"description": "Deployment-split governance status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_deployment_split_governance_status_route(
    request: Request,
) -> DeploymentSplitGovernanceStatusResponse:
    return build_deployment_split_governance_status(request.app.state)


@router.get(
    "/production-baseline/runtime-status",
    response_model=ProductionBaselineRuntimeStatusResponse,
    operation_id="getProductionBaselineRuntimeStatus",
    summary="Get RFC-0020 production-baseline runtime status",
    description=(
        "Returns the current lotus-ai production-baseline posture across the major dependencies "
        "needed to distinguish local or demo-capable runtime, prod-shaped local runtime, and "
        "production-ready runtime."
    ),
    responses={
        200: {"description": "Production-baseline runtime status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_production_baseline_runtime_status_route(
    request: Request,
) -> ProductionBaselineRuntimeStatusResponse:
    return build_production_baseline_runtime_status(request.app.state)


@router.get(
    "/production-baseline/activation-readiness",
    response_model=ProductionBaselineActivationReadinessResponse,
    operation_id="getProductionBaselineActivationReadiness",
    summary="Get RFC-0020 production-baseline activation readiness",
    description=(
        "Returns whether lotus-ai currently satisfies the technical runtime requirements "
        "to be treated as the accepted RFC-0020 production baseline."
    ),
    responses={
        200: {"description": "Production-baseline activation readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_production_baseline_activation_readiness_route(
    request: Request,
) -> ProductionBaselineActivationReadinessResponse:
    return build_production_baseline_activation_readiness(request.app.state)


@router.get(
    "/production-baseline/runbook-readiness",
    response_model=ProductionBaselineRunbookReadinessResponse,
    operation_id="getProductionBaselineRunbookReadiness",
    summary="Get RFC-0020 production-baseline runbook readiness",
    description=(
        "Returns the current operator-runbook posture for the accepted RFC-0020 production baseline."
    ),
    responses={
        200: {"description": "Production-baseline runbook readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_production_baseline_runbook_readiness_route() -> (
    ProductionBaselineRunbookReadinessResponse
):
    return build_production_baseline_runbook_readiness()


@router.get(
    "/production-baseline/governance-status",
    response_model=ProductionBaselineGovernanceStatusResponse,
    operation_id="getProductionBaselineGovernanceStatus",
    summary="Get RFC-0020 production-baseline governance status",
    description=(
        "Returns the composed runtime, activation, and runbook posture for the accepted "
        "RFC-0020 production baseline."
    ),
    responses={
        200: {"description": "Production-baseline governance status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_production_baseline_governance_status_route(
    request: Request,
) -> ProductionBaselineGovernanceStatusResponse:
    return build_production_baseline_governance_status(request.app.state)


@router.get(
    "/production-go-live/runtime-status",
    response_model=ProductionGoLiveRuntimeStatusResponse,
    operation_id="getProductionGoLiveRuntimeStatus",
    summary="Get RFC-0022 production go-live runtime status",
    description=(
        "Returns the current RFC-0022 production go-live posture across platform approval state, "
        "managed secret and object-storage approval domains, live-provider review posture, and the "
        "current named downstream use-case production state."
    ),
    responses={
        200: {"description": "Production go-live runtime status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_production_go_live_runtime_status_route(
    request: Request,
) -> ProductionGoLiveRuntimeStatusResponse:
    return build_production_go_live_runtime_status(request.app.state)


@router.get(
    "/production-go-live/activation-readiness",
    response_model=ProductionGoLiveActivationReadinessResponse,
    operation_id="getProductionGoLiveActivationReadiness",
    summary="Get RFC-0022 production go-live activation readiness",
    description=(
        "Returns whether lotus-ai currently satisfies the bounded production go-live approval "
        "requirements across platform approval, live-provider governance, and freeze posture."
    ),
    responses={
        200: {"description": "Production go-live activation readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_production_go_live_activation_readiness_route(
    request: Request,
) -> ProductionGoLiveActivationReadinessResponse:
    return build_production_go_live_activation_readiness(request.app.state)


@router.get(
    "/production-go-live/runbook-readiness",
    response_model=ProductionGoLiveRunbookReadinessResponse,
    operation_id="getProductionGoLiveRunbookReadiness",
    summary="Get RFC-0022 production go-live runbook readiness",
    description=(
        "Returns the current operator-runbook posture for managed-infrastructure review, live-provider freeze handling, and rollback guidance."
    ),
    responses={
        200: {"description": "Production go-live runbook readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_production_go_live_runbook_readiness_route() -> (
    ProductionGoLiveRunbookReadinessResponse
):
    return build_production_go_live_runbook_readiness()


@router.get(
    "/production-go-live/use-case-approval",
    response_model=ProductionGoLiveUseCaseApprovalResponse,
    operation_id="getProductionGoLiveUseCaseApproval",
    summary="Get RFC-0022 downstream use-case production approval",
    description=(
        "Returns the current active-production approval posture for the named downstream use case, including the separation between limited-rollout readiness and active-production approval."
    ),
    responses={
        200: {"description": "Production go-live use-case approval returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_production_go_live_use_case_approval_route(
    request: Request,
) -> ProductionGoLiveUseCaseApprovalResponse:
    return build_production_go_live_use_case_approval(request.app.state)


@router.get(
    "/production-go-live/governance-status",
    response_model=ProductionGoLiveGovernanceStatusResponse,
    operation_id="getProductionGoLiveGovernanceStatus",
    summary="Get RFC-0022 production go-live governance status",
    description=(
        "Returns the composed runtime, activation, and runbook posture for the current RFC-0022 production go-live boundary."
    ),
    responses={
        200: {"description": "Production go-live governance status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_production_go_live_governance_status_route(
    request: Request,
) -> ProductionGoLiveGovernanceStatusResponse:
    return build_production_go_live_governance_status(request.app.state)
