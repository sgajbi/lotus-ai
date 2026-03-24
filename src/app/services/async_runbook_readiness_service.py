from __future__ import annotations

from app.config import settings
from app.contracts.async_runtime import (
    AsyncRunbookReadinessItem,
    AsyncRunbookReadinessResponse,
)
from app.services.governance_readiness import summarize_activation_items


def build_async_runbook_readiness() -> AsyncRunbookReadinessResponse:
    items = [
        AsyncRunbookReadinessItem(
            runbook_id="async_operational_runbook",
            status="READY",
            required_for_activation=True,
            notes=(
                "The service runbook now documents dedicated worker startup, queue-backed cutover, "
                "drain mode, degraded fallback review, and rollback between governed cutover states."
            ),
        ),
        AsyncRunbookReadinessItem(
            runbook_id="async_oncall_and_escalation",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "On-call ownership, escalation flow, and incident triage playbooks for worker "
                "execution must be defined before activation."
            ),
        ),
        AsyncRunbookReadinessItem(
            runbook_id="async_capacity_and_replay_procedures",
            status="READY",
            required_for_activation=True,
            notes=(
                "Replay, requeue, abandon, lease-expiry recovery, queue backlog review, queue outage "
                "response, and worker drain procedures are now documented for the queue-backed worker path."
            ),
        ),
        AsyncRunbookReadinessItem(
            runbook_id="async_observability_incident_views",
            status="READY",
            required_for_activation=True,
            notes=(
                "Bounded async observability and incident-evidence summaries are now exposed through "
                "`/platform/observability/async-summary` and `/platform/observability/incident-summary`; "
                "external dashboards remain deployment-specific and are not an RFC-0013 activation gate."
            ),
        ),
    ]
    required_item_count, completed_required_item_count = summarize_activation_items(items)
    return AsyncRunbookReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        runbook_ready=completed_required_item_count == required_item_count,
        required_item_count=required_item_count,
        completed_required_item_count=completed_required_item_count,
        items=items,
    )
