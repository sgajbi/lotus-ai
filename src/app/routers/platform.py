from __future__ import annotations

from fastapi import APIRouter, Request

from app.contracts.platform import PlatformRuntimeStatusResponse
from app.contracts.production_baseline import (
    ProductionBaselineActivationReadinessResponse,
    ProductionBaselineGovernanceStatusResponse,
    ProductionBaselineRunbookReadinessResponse,
    ProductionBaselineRuntimeStatusResponse,
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
from app.services.platform_status import build_platform_runtime_status
from app.services.production_baseline_runtime import build_production_baseline_runtime_status

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
