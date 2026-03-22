from __future__ import annotations

from app.config import settings
from app.contracts.retrieval import (
    RetrievalRunbookReadinessItem,
    RetrievalRunbookReadinessResponse,
)


def build_retrieval_runbook_readiness() -> RetrievalRunbookReadinessResponse:
    items = [
        RetrievalRunbookReadinessItem(
            runbook_id="retrieval_operational_runbook",
            status="FOUNDATION_DOCUMENTED",
            required_for_activation=True,
            notes=(
                "Retrieval operating model is documented at a foundation level, but live search "
                "and indexing activation steps are not yet finalized."
            ),
        ),
        RetrievalRunbookReadinessItem(
            runbook_id="retrieval_oncall_and_escalation",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "On-call ownership, retrieval incident triage, and escalation procedures for "
                "live search and indexing must be defined before activation."
            ),
        ),
        RetrievalRunbookReadinessItem(
            runbook_id="retrieval_reindex_and_replay_procedures",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "Reindex, replay, failure recovery, and corpus refresh procedures are not yet "
                "documented."
            ),
        ),
        RetrievalRunbookReadinessItem(
            runbook_id="retrieval_observability_dashboard_pack",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "Dedicated retrieval latency, indexing backlog, citation quality, and search "
                "failure dashboards and alerts must be defined before activation."
            ),
        ),
    ]
    required_items = [item for item in items if item.required_for_activation]
    completed_required_items = [
        item for item in required_items if item.status in {"READY", "ACTIVATED"}
    ]
    return RetrievalRunbookReadinessResponse(
        service=settings.service_name,
        delivery_phase=settings.delivery_phase,
        runbook_ready=False,
        required_item_count=len(required_items),
        completed_required_item_count=len(completed_required_items),
        items=items,
    )
