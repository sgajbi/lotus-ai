from __future__ import annotations

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.evals import EvaluationFixtureDetailResponse
from app.evals.fixture_manifest import (
    EvaluationFixtureManifestValidationError,
    load_evaluation_fixture_family,
    load_evaluation_fixture_manifest,
)


def build_evaluation_fixture_detail(*, fixture_id: str) -> EvaluationFixtureDetailResponse:
    manifest = load_evaluation_fixture_manifest()
    try:
        fixture_family = load_evaluation_fixture_family(fixture_id=fixture_id)
    except EvaluationFixtureManifestValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation fixture family '{fixture_id}' was not found.",
        ) from exc

    return EvaluationFixtureDetailResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        manifest_version=manifest.manifest_version,
        fixture=fixture_family.descriptor,
        task_id=fixture_family.task_id,
        cases=fixture_family.cases,
    )
