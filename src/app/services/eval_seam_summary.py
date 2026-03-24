from __future__ import annotations

from app.contracts.evals import EvaluationAssetStatus, EvaluationSeamCoverageDescriptor
from app.services.eval_catalog import build_evaluation_catalog

SEAM_FIXTURE_MAP: dict[str, list[str]] = {
    "async_execution": ["async_runtime_examples"],
    "task_execution": [
        "task_capability_contracts",
        "explanation_task_examples",
        "summarization_task_examples",
        "lotus_performance_first_use_case_examples",
    ],
    "prompt_rollout": [
        "prompt_promotion_examples",
        "prompt_rollback_examples",
    ],
    "retrieval": ["retrieval_citation_examples"],
    "provider_execution": [
        "provider_policy_examples",
        "provider_runtime_examples",
        "provider_failure_mode_examples",
        "provider_operations_examples",
        "provider_degradation_examples",
    ],
    "safety_execution": [
        "safety_policy_examples",
        "safety_runtime_examples",
    ],
}


def build_evaluation_seam_coverage() -> list[EvaluationSeamCoverageDescriptor]:
    catalog = build_evaluation_catalog()
    fixture_lookup = {fixture.fixture_id: fixture for fixture in catalog.fixture_families}
    seam_coverage: list[EvaluationSeamCoverageDescriptor] = []
    for seam_id, fixture_ids in SEAM_FIXTURE_MAP.items():
        staged_fixtures = [
            fixture_lookup[fixture_id]
            for fixture_id in fixture_ids
            if fixture_id in fixture_lookup
            and fixture_lookup[fixture_id].status == EvaluationAssetStatus.STAGED
        ]
        seam_coverage.append(
            EvaluationSeamCoverageDescriptor(
                seam_id=seam_id,
                fixture_ids=[fixture.fixture_id for fixture in staged_fixtures],
                staged_fixture_count=len(staged_fixtures),
                staged_case_count=sum(fixture.case_count for fixture in staged_fixtures),
            )
        )
    return seam_coverage
