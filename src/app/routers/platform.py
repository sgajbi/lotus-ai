from __future__ import annotations

from fastapi import APIRouter, Request

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
from app.services.production_baseline_governance import (
    build_production_baseline_governance_status,
)
from app.services.production_baseline_runbook_readiness import (
    build_production_baseline_runbook_readiness,
)
from app.services.deployment_split_activation_readiness import (
    build_deployment_split_activation_readiness,
)
from app.services.deployment_split_governance import build_deployment_split_governance_status
from app.services.deployment_split_runbook_readiness import (
    build_deployment_split_runbook_readiness,
)
from app.services.platform_status import build_platform_runtime_status
from app.services.deployment_split_runtime import build_deployment_split_runtime_status
from app.services.production_baseline_runtime import build_production_baseline_runtime_status
from app.services.resilience_activation_readiness import build_resilience_activation_readiness
from app.services.resilience_drill_evidence import build_resilience_drill_evidence
from app.services.resilience_governance import build_resilience_governance_status
from app.services.resilience_restore_plan import build_resilience_restore_plan
from app.services.resilience_runbook_readiness import build_resilience_runbook_readiness
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
