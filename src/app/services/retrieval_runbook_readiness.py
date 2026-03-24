from __future__ import annotations

from app.config import settings
from app.contracts.retrieval import (
    RetrievalRunbookReadinessItem,
    RetrievalRunbookReadinessResponse,
)
from app.services.governance_readiness import summarize_activation_items


def build_retrieval_runbook_readiness() -> RetrievalRunbookReadinessResponse:
    items = [
        RetrievalRunbookReadinessItem(
            runbook_id="retrieval_operational_runbook",
            status="READY",
            required_for_activation=True,
            notes=(
                "The service runbook now documents live-search rollout review, runtime-backed "
                "approval-gate checks, and operator-facing retrieval status surfaces."
            ),
        ),
        RetrievalRunbookReadinessItem(
            runbook_id="retrieval_oncall_and_escalation",
            status="FOUNDATION_DOCUMENTED",
            required_for_activation=True,
            notes=(
                "Retrieval governance and operator review flow are documented, but named on-call "
                "ownership and formal escalation rotation are still not approved."
            ),
        ),
        RetrievalRunbookReadinessItem(
            runbook_id="retrieval_reindex_and_replay_procedures",
            status="READY",
            required_for_activation=True,
            notes=(
                "The runbook now documents runtime-backed retrieval rollout plus reindex, replay, "
                "rollback, and corpus-recovery expectations for the live-search path."
            ),
        ),
        RetrievalRunbookReadinessItem(
            runbook_id="retrieval_embedding_dependency_review",
            status="FOUNDATION_DOCUMENTED",
            required_for_activation=True,
            notes=(
                "Retrieval indexing now documents how bounded live embedding posture is reviewed separately from broader retrieval go-live approval."
            ),
        ),
        RetrievalRunbookReadinessItem(
            runbook_id="retrieval_corpus_change_review",
            status="FOUNDATION_DOCUMENTED",
            required_for_activation=True,
            notes=(
                "Corpus refresh, withdrawal, and search-eligibility review are now runtime-visible, but final operational review procedures are still being hardened."
            ),
        ),
        RetrievalRunbookReadinessItem(
            runbook_id="retrieval_observability_incident_views",
            status="READY",
            required_for_activation=True,
            notes=(
                "Bounded retrieval observability and incident-evidence summaries are now exposed through "
                "`/platform/observability/retrieval-summary` and `/platform/observability/incident-summary`; "
                "external dashboards remain deployment-specific and are not an RFC-0013 activation gate."
            ),
        ),
    ]
    required_item_count, completed_required_item_count = summarize_activation_items(items)
    return RetrievalRunbookReadinessResponse(
        service=settings.service_name,
        delivery_phase=settings.delivery_phase,
        runbook_ready=completed_required_item_count == required_item_count,
        required_item_count=required_item_count,
        completed_required_item_count=completed_required_item_count,
        items=items,
    )
