from __future__ import annotations

from app.contracts.evals import (
    EvaluationAssetStatus,
    EvaluationRuntimeStatusResponse,
)
from app.services.eval_catalog import build_evaluation_catalog


def build_evaluation_runtime_status() -> EvaluationRuntimeStatusResponse:
    catalog = build_evaluation_catalog()
    staged_fixture_count = sum(
        1 for fixture in catalog.fixture_families if fixture.status == EvaluationAssetStatus.STAGED
    )
    documented_fixture_count = sum(
        1
        for fixture in catalog.fixture_families
        if fixture.status == EvaluationAssetStatus.DOCUMENTED
    )
    return EvaluationRuntimeStatusResponse(
        service=catalog.service,
        version=catalog.version,
        delivery_phase=catalog.delivery_phase,
        evidence_category_count=len(catalog.evidence_categories),
        staged_fixture_count=staged_fixture_count,
        documented_fixture_count=documented_fixture_count,
        evaluation_runner_active=False,
        message=(
            "Evaluation assets are cataloged and partially staged, but no live evaluation runner "
            "is active in the foundation phase."
        ),
    )
