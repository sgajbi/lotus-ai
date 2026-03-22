from __future__ import annotations

from fastapi import APIRouter

from app.contracts.providers import ProviderCatalogResponse, ProviderPolicyResponse
from app.services.provider_catalog import build_provider_catalog
from app.services.provider_policy import build_provider_policy

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


@router.get(
    "/policy",
    response_model=ProviderPolicyResponse,
    operation_id="getProviderPolicy",
    summary="Get lotus-ai provider execution policy",
    description=(
        "Returns the governed provider execution policy for lotus-ai, including supported modes "
        "and rejection behavior for the current phase."
    ),
    responses={
        200: {"description": "Provider execution policy returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_provider_policy_route() -> ProviderPolicyResponse:
    return build_provider_policy()
