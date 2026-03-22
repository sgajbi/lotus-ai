from __future__ import annotations

from dataclasses import dataclass

from app.contracts.evals import EvaluationAssetStatus, EvaluationRunStatus
from app.services.eval_catalog import build_evaluation_catalog
from app.services.eval_run_service import build_evaluation_run_catalog

_PROVIDER_EXECUTION_SEAM_ID = "provider_execution"


@dataclass(frozen=True)
class ProviderEvidenceInventory:
    staged_fixture_ids: frozenset[str]
    evidence_category_ids: frozenset[str]
    recorded_provider_fixture_ids: frozenset[str]
    latest_recorded_provider_run_id: str | None


def build_provider_evidence_inventory() -> ProviderEvidenceInventory:
    catalog = build_evaluation_catalog()
    run_catalog = build_evaluation_run_catalog()

    staged_fixture_ids = frozenset(
        fixture.fixture_id
        for fixture in catalog.fixture_families
        if fixture.status == EvaluationAssetStatus.STAGED
    )
    evidence_category_ids = frozenset(
        category.category_id for category in catalog.evidence_categories
    )

    recorded_provider_fixture_ids: set[str] = set()
    latest_recorded_provider_run_id: str | None = None
    for run in run_catalog.runs:
        if run.status != EvaluationRunStatus.RECORDED:
            continue
        seam = next(
            (
                coverage
                for coverage in run.seam_coverage
                if coverage.seam_id == _PROVIDER_EXECUTION_SEAM_ID
            ),
            None,
        )
        if seam is None:
            continue
        if latest_recorded_provider_run_id is None:
            latest_recorded_provider_run_id = run.run_id
        recorded_provider_fixture_ids.update(seam.fixture_ids)

    return ProviderEvidenceInventory(
        staged_fixture_ids=staged_fixture_ids,
        evidence_category_ids=evidence_category_ids,
        recorded_provider_fixture_ids=frozenset(recorded_provider_fixture_ids),
        latest_recorded_provider_run_id=latest_recorded_provider_run_id,
    )
