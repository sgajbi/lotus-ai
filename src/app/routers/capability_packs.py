from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.contracts.capability_packs import (
    CapabilityPackActivationReadinessResponse,
    CapabilityPackAdoptionTemplateResponse,
    CapabilityPackCatalogGovernanceStatusResponse,
    CapabilityPackCatalogResponse,
    CapabilityPackDetailResponse,
    CapabilityPackGovernanceStatusResponse,
    CapabilityPackObservabilitySummaryResponse,
    CapabilityPackRunbookReadinessResponse,
)
from app.services.capability_pack_catalog import (
    build_capability_pack_catalog,
    build_capability_pack_detail,
)
from app.services.capability_pack_activation_readiness import (
    build_capability_pack_activation_readiness,
)
from app.services.capability_pack_adoption_template import (
    build_capability_pack_adoption_template,
)
from app.services.capability_pack_governance import (
    build_capability_pack_catalog_governance_status,
    build_capability_pack_governance_status,
)
from app.services.capability_pack_observability import (
    build_capability_pack_observability_summary,
)
from app.services.capability_pack_runbook_readiness import (
    build_capability_pack_runbook_readiness,
)

router = APIRouter(tags=["platform"])


@router.get(
    "/platform/capability-packs",
    response_model=CapabilityPackCatalogResponse,
    operation_id="getCapabilityPackCatalog",
    summary="Get lotus-ai capability-pack catalog",
    description=(
        "Returns the current app-facing capability-pack catalog exposed by lotus-ai. "
        "This catalog is intentionally distinct from the generic task catalog and describes "
        "product-layer capability shape, maturity, and governance surfaces."
    ),
    responses={
        200: {"description": "Capability-pack catalog returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_capability_pack_catalog() -> CapabilityPackCatalogResponse:
    return build_capability_pack_catalog()


@router.get(
    "/platform/capability-packs/governance-status",
    response_model=CapabilityPackCatalogGovernanceStatusResponse,
    operation_id="getCapabilityPackCatalogGovernanceStatus",
    summary="Get lotus-ai capability-pack catalog governance status",
    description=(
        "Returns the catalog-level governance posture across all currently modeled capability packs."
    ),
    responses={
        200: {"description": "Capability-pack catalog governance returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_capability_pack_catalog_governance_status_route() -> (
    CapabilityPackCatalogGovernanceStatusResponse
):
    return build_capability_pack_catalog_governance_status()


@router.get(
    "/platform/capability-packs/{pack_id}",
    response_model=CapabilityPackDetailResponse,
    operation_id="getCapabilityPackDetail",
    summary="Get lotus-ai capability-pack detail",
    description=(
        "Returns pack-specific quality expectations, unsupported-input posture, and product-layer "
        "non-goals for one app-facing capability pack."
    ),
    responses={
        200: {"description": "Capability-pack detail returned successfully."},
        404: {"description": "Capability pack not found."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_capability_pack_detail(pack_id: str) -> CapabilityPackDetailResponse:
    try:
        return build_capability_pack_detail(pack_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/platform/capability-packs/{pack_id}/adoption-template",
    response_model=CapabilityPackAdoptionTemplateResponse,
    operation_id="getCapabilityPackAdoptionTemplate",
    summary="Get lotus-ai capability-pack adoption template",
    description=(
        "Returns the pack-native downstream onboarding template for one app-facing capability pack."
    ),
    responses={
        200: {"description": "Capability-pack adoption template returned successfully."},
        404: {"description": "Capability pack not found."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_capability_pack_adoption_template(
    pack_id: str,
) -> CapabilityPackAdoptionTemplateResponse:
    try:
        return build_capability_pack_adoption_template(pack_id=pack_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/platform/capability-packs/{pack_id}/observability-summary",
    response_model=CapabilityPackObservabilitySummaryResponse,
    operation_id="getCapabilityPackObservabilitySummary",
    summary="Get lotus-ai capability-pack observability summary",
    description=(
        "Returns the bounded audit, async, and support-review observability summary for one "
        "app-facing capability pack."
    ),
    responses={
        200: {"description": "Capability-pack observability summary returned successfully."},
        404: {"description": "Capability pack not found."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_capability_pack_observability_summary(
    pack_id: str,
) -> CapabilityPackObservabilitySummaryResponse:
    try:
        return build_capability_pack_observability_summary(pack_id=pack_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/platform/capability-packs/{pack_id}/activation-readiness",
    response_model=CapabilityPackActivationReadinessResponse,
    operation_id="getCapabilityPackActivationReadiness",
    summary="Get lotus-ai capability-pack activation readiness",
    description=(
        "Returns the bounded activation-readiness posture for one app-facing capability pack."
    ),
    responses={
        200: {"description": "Capability-pack activation readiness returned successfully."},
        404: {"description": "Capability pack not found."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_capability_pack_activation_readiness(
    pack_id: str,
) -> CapabilityPackActivationReadinessResponse:
    try:
        return build_capability_pack_activation_readiness(pack_id=pack_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/platform/capability-packs/{pack_id}/runbook-readiness",
    response_model=CapabilityPackRunbookReadinessResponse,
    operation_id="getCapabilityPackRunbookReadiness",
    summary="Get lotus-ai capability-pack runbook readiness",
    description=(
        "Returns the bounded runbook-readiness posture for one app-facing capability pack."
    ),
    responses={
        200: {"description": "Capability-pack runbook readiness returned successfully."},
        404: {"description": "Capability pack not found."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_capability_pack_runbook_readiness(
    pack_id: str,
) -> CapabilityPackRunbookReadinessResponse:
    try:
        return build_capability_pack_runbook_readiness(pack_id=pack_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/platform/capability-packs/{pack_id}/governance-status",
    response_model=CapabilityPackGovernanceStatusResponse,
    operation_id="getCapabilityPackGovernanceStatus",
    summary="Get lotus-ai capability-pack governance status",
    description=(
        "Returns the composed activation, runbook, and observability governance posture for one "
        "app-facing capability pack."
    ),
    responses={
        200: {"description": "Capability-pack governance returned successfully."},
        404: {"description": "Capability pack not found."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_capability_pack_governance_status(
    pack_id: str,
) -> CapabilityPackGovernanceStatusResponse:
    try:
        return build_capability_pack_governance_status(pack_id=pack_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
