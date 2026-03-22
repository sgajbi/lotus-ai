from __future__ import annotations

from fastapi import APIRouter

from app.contracts.evals import EvaluationCatalogResponse
from app.services.eval_catalog import build_evaluation_catalog

router = APIRouter(prefix="/platform/evals", tags=["platform"])


@router.get(
    "/catalog",
    response_model=EvaluationCatalogResponse,
    operation_id="getEvaluationCatalog",
    summary="Get lotus-ai evaluation catalog",
    description=(
        "Returns the current lotus-ai evaluation catalog, including execution evidence "
        "categories and staged fixture families for regression and governance workflows."
    ),
    responses={
        200: {"description": "Evaluation catalog returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_evaluation_catalog_route() -> EvaluationCatalogResponse:
    return build_evaluation_catalog()
