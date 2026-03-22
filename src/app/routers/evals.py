from __future__ import annotations

from fastapi import APIRouter

from app.contracts.evals import (
    EvaluationCatalogResponse,
    EvaluationFixtureDetailResponse,
    EvaluationRuntimeStatusResponse,
)
from app.services.eval_catalog import build_evaluation_catalog
from app.services.eval_fixture_service import build_evaluation_fixture_detail
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


@router.get(
    "/fixtures/{fixture_id}",
    response_model=EvaluationFixtureDetailResponse,
    operation_id="getEvaluationFixtureDetail",
    summary="Get lotus-ai evaluation fixture family detail",
    description=(
        "Returns governed detail for a specific evaluation fixture family, including case-level "
        "metadata without exposing raw mutable evaluation payloads."
    ),
    responses={
        200: {"description": "Evaluation fixture family detail returned successfully."},
        404: {"description": "Evaluation fixture family not found."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_evaluation_fixture_detail_route(fixture_id: str) -> EvaluationFixtureDetailResponse:
    return build_evaluation_fixture_detail(fixture_id=fixture_id)
