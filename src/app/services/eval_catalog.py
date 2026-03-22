from __future__ import annotations

from app.config import settings
from app.contracts.evals import EvaluationCatalogResponse
from app.evals.fixture_manifest import load_evaluation_fixture_manifest


def build_evaluation_catalog() -> EvaluationCatalogResponse:
    manifest = load_evaluation_fixture_manifest()
    return EvaluationCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        manifest_version=manifest.manifest_version,
        evidence_categories=manifest.evidence_categories,
        fixture_families=manifest.fixture_families,
    )
