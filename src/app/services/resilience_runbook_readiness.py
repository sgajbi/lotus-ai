from __future__ import annotations

from app.config import settings
from app.contracts.resilience import (
    ResilienceRunbookReadinessItem,
    ResilienceRunbookReadinessResponse,
)
from app.services.governance_readiness import summarize_activation_items


def build_resilience_runbook_readiness() -> ResilienceRunbookReadinessResponse:
    items = [
        ResilienceRunbookReadinessItem(
            runbook_id="resilience_restore_ordering_review",
            status="READY",
            required_for_activation=True,
            notes="The service runbook now documents the restore-order review flow and the boundary between restoring durable state and re-enabling broader rollout.",
        ),
        ResilienceRunbookReadinessItem(
            runbook_id="resilience_queue_and_worker_recovery_review",
            status="READY",
            required_for_activation=True,
            notes="Queue-backed async recovery and dedicated-worker review paths are documented explicitly, including degraded posture handling.",
        ),
        ResilienceRunbookReadinessItem(
            runbook_id="resilience_provider_and_retrieval_recovery_review",
            status="READY",
            required_for_activation=True,
            notes="Provider and retrieval recovery review is documented as a validation step after internal state restore rather than part of relational recovery itself.",
        ),
        ResilienceRunbookReadinessItem(
            runbook_id="resilience_drill_and_incident_review_boundary",
            status="READY",
            required_for_activation=True,
            notes="The runbook now distinguishes current drill evidence, restored-with-findings posture, and incident review boundaries clearly enough for governance review.",
        ),
    ]
    required_item_count, completed_required_item_count = summarize_activation_items(items)
    return ResilienceRunbookReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        runbook_ready=required_item_count == completed_required_item_count,
        required_item_count=required_item_count,
        completed_required_item_count=completed_required_item_count,
        items=items,
    )
