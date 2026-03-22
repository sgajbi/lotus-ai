from __future__ import annotations

from fastapi import APIRouter

from app.contracts.providers import ProviderCatalogResponse
from app.services.provider_catalog import build_provider_catalog

router = APIRouter(prefix="/platform/providers", tags=["platform"])


@router.get(
    "",
    response_model=ProviderCatalogResponse,
    operation_id="getProviderCatalog",
    summary="Get lotus-ai provider catalog",
    description=(
        "Returns the governed provider catalog for lotus-ai, including which provider paths are "
        "documented, disabled, or enabled for execution in the current phase."
    ),
    responses={
        200: {"description": "Provider catalog returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_provider_catalog_route() -> ProviderCatalogResponse:
    return build_provider_catalog()
