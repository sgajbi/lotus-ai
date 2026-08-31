from __future__ import annotations

from fastapi import APIRouter, Query

from app.contracts.artifacts import (
    ArtifactActivationReadinessResponse,
    ArtifactCatalogResponse,
    ArtifactGovernanceStatusResponse,
    ArtifactRunbookReadinessResponse,
    ArtifactRuntimeStatusResponse,
)
from app.services.artifact_activation_readiness import build_artifact_activation_readiness
from app.services.artifact_catalog import build_artifact_catalog
from app.services.artifact_governance import build_artifact_governance_status
from app.services.readiness_catalog import build_artifact_runbook_readiness
from app.services.artifact_runtime import build_artifact_runtime_status

router = APIRouter(prefix="/platform/artifacts", tags=["platform"])


@router.get(
    "/runtime-status",
    response_model=ArtifactRuntimeStatusResponse,
    operation_id="getArtifactRuntimeStatus",
    summary="Get artifact storage runtime status",
    description=(
        "Returns the governed artifact metadata and object-store posture for lotus-ai, including "
        "bounded status for the relational metadata layer and configured payload-store backend."
    ),
    responses={
        200: {"description": "Artifact runtime status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_artifact_runtime_status_route() -> ArtifactRuntimeStatusResponse:
    return build_artifact_runtime_status()


@router.get(
    "",
    response_model=ArtifactCatalogResponse,
    operation_id="getArtifactCatalog",
    summary="Get artifact catalog",
    description=(
        "Returns a bounded descriptor-first catalog of governed artifacts without exposing raw payloads "
        "or backend storage URLs."
    ),
)
async def get_artifact_catalog_route(
    limit: int = Query(default=50, ge=1, le=200),
    domain: str | None = Query(default=None),
) -> ArtifactCatalogResponse:
    return build_artifact_catalog(limit=limit, domain=domain)


@router.get(
    "/activation-readiness",
    response_model=ArtifactActivationReadinessResponse,
    operation_id="getArtifactActivationReadiness",
    summary="Get artifact activation readiness",
    description=(
        "Returns the technical activation-readiness posture for the governed artifact backbone, "
        "including durable store requirements and current runtime consumer cutover coverage."
    ),
    responses={
        200: {"description": "Artifact activation readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_artifact_activation_readiness_route() -> ArtifactActivationReadinessResponse:
    return build_artifact_activation_readiness()


@router.get(
    "/runbook-readiness",
    response_model=ArtifactRunbookReadinessResponse,
    operation_id="getArtifactRunbookReadiness",
    summary="Get artifact runbook readiness",
    description=(
        "Returns the operational runbook-readiness posture for governed artifact retention, "
        "incident-bundle review, and archive handling."
    ),
    responses={
        200: {"description": "Artifact runbook readiness returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_artifact_runbook_readiness_route() -> ArtifactRunbookReadinessResponse:
    return build_artifact_runbook_readiness()


@router.get(
    "/governance-status",
    response_model=ArtifactGovernanceStatusResponse,
    operation_id="getArtifactGovernanceStatus",
    summary="Get artifact governance status",
    description=(
        "Returns the composed governance posture for the governed artifact backbone by combining "
        "runtime, activation-readiness, and runbook-readiness views."
    ),
    responses={
        200: {"description": "Artifact governance status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_artifact_governance_status_route() -> ArtifactGovernanceStatusResponse:
    return build_artifact_governance_status()
