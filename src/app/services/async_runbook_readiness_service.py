from __future__ import annotations

from app.config import settings
from app.contracts.async_runtime import (
    AsyncRunbookReadinessItem,
    AsyncRunbookReadinessResponse,
)


def build_async_runbook_readiness() -> AsyncRunbookReadinessResponse:
    items = [
        AsyncRunbookReadinessItem(
            runbook_id="async_operational_runbook",
            status="FOUNDATION_DOCUMENTED",
            required_for_activation=True,
            notes=(
                "The async operating model is documented at a foundation level, but live-worker "
                "activation steps are not yet finalized."
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
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "Capacity management, backlog recovery, replay, and dead-letter handling "
                "procedures are not yet documented."
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
    required_items = [item for item in items if item.required_for_activation]
    completed_required_items = [
        item for item in required_items if item.status in {"READY", "ACTIVATED"}
    ]
    return AsyncRunbookReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        runbook_ready=False,
        required_item_count=len(required_items),
        completed_required_item_count=len(completed_required_items),
        items=items,
    )
