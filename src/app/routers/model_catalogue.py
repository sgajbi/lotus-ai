from __future__ import annotations

from fastapi import APIRouter

from app.contracts.model_catalogue import ModelCatalogueResponse
from app.services.model_catalogue import build_model_catalogue_response

router = APIRouter(prefix="/platform/models", tags=["platform"])


@router.get(
    "/catalogue",
    response_model=ModelCatalogueResponse,
    operation_id="getModelCatalogue",
    summary="Get the governed model catalogue",
    description=(
        "Returns the governed model catalogue for lotus-ai: every configured model identity as "
        "a first-class entry with provider, family, exact revision, deployment, SKU, lifecycle "
        "state, approval evidence and pinning posture. Reads are idempotently reconciled with "
        "the configured live-text settings and the approved workflow-run model-risk inventory."
    ),
    responses={
        200: {"description": "Model catalogue returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_model_catalogue_route() -> ModelCatalogueResponse:
    return build_model_catalogue_response()
