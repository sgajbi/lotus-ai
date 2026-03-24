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
            status="PARTIALLY_COMPLETE",
            required_for_activation=True,
            notes=(
                "The durable async operating model now includes queue-backed dedicated workers, "
                "explicit degraded fallback posture, and bounded worker-drain behavior, but final "
                "operator startup and cutover procedures remain incomplete."
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
            status="PARTIALLY_COMPLETE",
            required_for_activation=True,
            notes=(
                "Replay, lease-expiry recovery, bounded backlog visibility, and worker drain controls "
                "now exist for the queue-backed worker path, but final queue-outage and capacity "
                "runbooks are not yet activation-ready."
            ),
        ),
        AsyncRunbookReadinessItem(
            runbook_id="async_observability_dashboard_pack",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "Dedicated queue and worker dashboards, alerts, and supportability views must be "
                "defined before activation."
            ),
        ),
    ]
    required_item_count, completed_required_item_count = summarize_activation_items(items)
    return AsyncRunbookReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        runbook_ready=False,
        required_item_count=required_item_count,
        completed_required_item_count=completed_required_item_count,
        items=items,
    )
