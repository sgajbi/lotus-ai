from __future__ import annotations

from fastapi import APIRouter

from app.contracts.evals import EvaluationCatalogResponse, EvaluationRuntimeStatusResponse
from app.services.eval_catalog import build_evaluation_catalog
from app.services.eval_status import build_evaluation_runtime_status

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


@router.get(
    "/runtime-status",
    response_model=EvaluationRuntimeStatusResponse,
    operation_id="getEvaluationRuntimeStatus",
    summary="Get lotus-ai evaluation runtime status",
    description=(
        "Returns the current runtime posture for lotus-ai evaluation assets, including evidence "
        "category coverage and staged fixture readiness."
    ),
    responses={
        200: {"description": "Evaluation runtime status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_evaluation_runtime_status_route() -> EvaluationRuntimeStatusResponse:
    return build_evaluation_runtime_status()
