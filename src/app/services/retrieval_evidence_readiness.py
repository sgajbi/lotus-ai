from __future__ import annotations

from app.config import settings
from app.contracts.retrieval import (
    RetrievalEvidenceReadinessItem,
    RetrievalEvidenceReadinessResponse,
)
from app.services.governance_readiness import summarize_activation_items


def build_retrieval_evidence_readiness() -> RetrievalEvidenceReadinessResponse:
    items = [
        RetrievalEvidenceReadinessItem(
            evidence_id="retrieval_fixture_coverage_pack",
            status="FOUNDATION_STAGED",
            required_for_activation=True,
            notes=(
                "Foundation-phase retrieval fixtures exist, but a retrieval-specific live "
                "activation evidence pack is not yet approved."
            ),
        ),
        RetrievalEvidenceReadinessItem(
            evidence_id="retrieval_regression_run_baseline",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "A governed regression-run baseline proving retrieval search, citation, and "
                "refusal behavior for rollout candidates is not yet recorded."
            ),
        ),
        RetrievalEvidenceReadinessItem(
            evidence_id="retrieval_citation_traceability_pack",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "Activation review evidence linking indexed sources, citations, and runtime "
                "search traces is not yet assembled."
            ),
        ),
        RetrievalEvidenceReadinessItem(
            evidence_id="retrieval_reindex_and_rollback_evidence_pack",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "Reindex, rollback, and corpus-recovery evidence proving safe reversion behavior "
                "is not yet documented."
            ),
        ),
    ]
    required_item_count, completed_required_item_count = summarize_activation_items(items)
    return RetrievalEvidenceReadinessResponse(
        service=settings.service_name,
        delivery_phase=settings.delivery_phase,
        evidence_ready=False,
        required_item_count=required_item_count,
        completed_required_item_count=completed_required_item_count,
        items=items,
    )
