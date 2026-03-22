from __future__ import annotations

from app.config import settings
from app.contracts.providers import (
    ProviderRunbookReadinessItem,
    ProviderRunbookReadinessResponse,
)


def build_provider_runbook_readiness() -> ProviderRunbookReadinessResponse:
    items = [
        ProviderRunbookReadinessItem(
            runbook_id="provider_operational_runbook",
            status="FOUNDATION_DOCUMENTED",
            required_for_activation=True,
            notes=(
                "Provider operating model is documented at a foundation level, but live-provider "
                "activation steps are not yet finalized."
            ),
        ),
        ProviderRunbookReadinessItem(
            runbook_id="provider_oncall_and_escalation",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "On-call ownership, vendor escalation path, and incident triage playbooks for "
                "live provider execution must be defined before activation."
            ),
        ),
        ProviderRunbookReadinessItem(
            runbook_id="provider_cost_and_rate_limit_controls",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "Runbooks for provider usage limits, rate-limit incidents, and cost-protection "
                "responses are not yet documented."
            ),
        ),
        ProviderRunbookReadinessItem(
            runbook_id="provider_observability_dashboard_pack",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "Dedicated provider latency, failure, and quota dashboards and alerts must be "
                "defined before activation."
            ),
        ),
    ]
    required_items = [item for item in items if item.required_for_activation]
    completed_required_items = [
        item for item in required_items if item.status in {"READY", "ACTIVATED"}
    ]
    return ProviderRunbookReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        runbook_ready=False,
        required_item_count=len(required_items),
        completed_required_item_count=len(completed_required_items),
        items=items,
    )
