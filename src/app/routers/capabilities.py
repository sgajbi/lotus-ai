from __future__ import annotations

from fastapi import APIRouter

from app.contracts.tasks import CapabilityCatalogResponse
from app.services.capability_catalog import build_capability_catalog

router = APIRouter(tags=["platform"])


@router.get(
    "/platform/capabilities",
    response_model=CapabilityCatalogResponse,
    summary="Get lotus-ai capability catalog",
    description=(
        "Returns the current bounded AI task capabilities exposed by lotus-ai. "
        "This endpoint is intended for upstream Lotus services and platforms to discover "
        "which task classes are available during the current delivery phase."
    ),
    responses={
        200: {"description": "Capability catalog returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_platform_capabilities() -> CapabilityCatalogResponse:
    return build_capability_catalog()
