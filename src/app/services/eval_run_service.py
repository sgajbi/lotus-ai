from __future__ import annotations

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.evals import (
    EvaluationRunCatalogResponse,
    EvaluationRunDetailResponse,
    EvaluationRunStatus,
)
from app.evals.run_registry import load_evaluation_run_artifacts


def build_evaluation_run_catalog() -> EvaluationRunCatalogResponse:
    runs = load_evaluation_run_artifacts()
    latest_run_id = runs[0].run_id if runs else None
    status_counts = {
        status: sum(1 for run in runs if run.status == status) for status in EvaluationRunStatus
    }
    return EvaluationRunCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        run_count=len(runs),
        latest_run_id=latest_run_id,
        status_counts=status_counts,
        runs=runs,
    )


def build_evaluation_run_detail(*, run_id: str) -> EvaluationRunDetailResponse:
    runs = load_evaluation_run_artifacts()
    run = next((item for item in runs if item.run_id == run_id), None)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation run artifact '{run_id}' was not found.",
        )
    return EvaluationRunDetailResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        run=run,
    )
