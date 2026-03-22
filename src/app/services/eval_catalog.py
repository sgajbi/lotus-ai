from __future__ import annotations

from app.config import settings
from app.contracts.evals import (
    EvaluationAssetStatus,
    EvaluationCatalogResponse,
    EvaluationEvidenceCategoryDescriptor,
    EvaluationFixtureDescriptor,
)


def build_evaluation_catalog() -> EvaluationCatalogResponse:
    return EvaluationCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        evidence_categories=[
            EvaluationEvidenceCategoryDescriptor(
                category_id="task_contract",
                description="Bounded task contract and caller selection evidence.",
            ),
            EvaluationEvidenceCategoryDescriptor(
                category_id="prompt_selection",
                description="Resolved prompt version and management provenance evidence.",
            ),
            EvaluationEvidenceCategoryDescriptor(
                category_id="provider_resolution",
                description="Provider gateway and execution-path resolution evidence.",
            ),
            EvaluationEvidenceCategoryDescriptor(
                category_id="safety_outcome",
                description="Applied safety posture and enforced-control evidence.",
            ),
            EvaluationEvidenceCategoryDescriptor(
                category_id="retrieval_posture",
                description="Current retrieval execution posture captured at task runtime.",
            ),
        ],
        fixture_families=[
            EvaluationFixtureDescriptor(
                fixture_id="task_capability_contracts",
                status=EvaluationAssetStatus.STAGED,
                description="Contract fixtures covering supported task surfaces and policy behavior.",
            ),
            EvaluationFixtureDescriptor(
                fixture_id="explanation_task_examples",
                status=EvaluationAssetStatus.DOCUMENTED,
                description="Golden examples for explanation-oriented tasks.",
            ),
            EvaluationFixtureDescriptor(
                fixture_id="summarization_task_examples",
                status=EvaluationAssetStatus.DOCUMENTED,
                description="Golden examples for summarization-oriented tasks.",
            ),
            EvaluationFixtureDescriptor(
                fixture_id="retrieval_citation_examples",
                status=EvaluationAssetStatus.DOCUMENTED,
                description="Retrieval citation and refusal evaluation examples for later activation.",
            ),
        ],
    )
