from __future__ import annotations

from dataclasses import dataclass

from app.contracts.evals import EvaluationAssetStatus, EvaluationCatalogResponse


@dataclass(frozen=True)
class EvaluationInventorySummary:
    evidence_category_count: int
    staged_fixture_count: int
    documented_fixture_count: int
    staged_case_count: int


def summarize_evaluation_inventory(
    catalog: EvaluationCatalogResponse,
) -> EvaluationInventorySummary:
    return EvaluationInventorySummary(
        evidence_category_count=len(catalog.evidence_categories),
        staged_fixture_count=sum(
            1
            for fixture in catalog.fixture_families
            if fixture.status == EvaluationAssetStatus.STAGED
        ),
        documented_fixture_count=sum(
            1
            for fixture in catalog.fixture_families
            if fixture.status == EvaluationAssetStatus.DOCUMENTED
        ),
        staged_case_count=sum(fixture.case_count for fixture in catalog.fixture_families),
    )
