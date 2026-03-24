from __future__ import annotations

from app.config import settings
from app.contracts.observability import (
    ObservabilityRunbookReadinessItem,
    ObservabilityRunbookReadinessResponse,
)
from app.services.governance_readiness import summarize_activation_items


def build_observability_runbook_readiness() -> ObservabilityRunbookReadinessResponse:
    items = [
        ObservabilityRunbookReadinessItem(
            runbook_id="observability_operational_review",
            status="READY",
            required_for_activation=True,
            notes="The service runbook now documents the observability API surface and the primary runtime and incident-summary review flow.",
        ),
        ObservabilityRunbookReadinessItem(
            runbook_id="observability_incident_review_and_correlation",
            status="READY",
            required_for_activation=True,
            notes="Incident review now uses bounded domain summaries, incident evidence, audit records, and existing correlation identifiers rather than ad hoc endpoint stitching.",
        ),
        ObservabilityRunbookReadinessItem(
            runbook_id="observability_breakdown_review_and_authorization",
            status="READY",
            required_for_activation=True,
            notes="Caller, tenant, and capability breakdown review is documented explicitly, including the authorization-aware tenant visibility rule.",
        ),
        ObservabilityRunbookReadinessItem(
            runbook_id="observability_external_dashboard_posture",
            status="DOCUMENTED_OUT_OF_SCOPE",
            required_for_activation=False,
            notes="RFC-0013 delivers in-service observability contracts and incident-evidence APIs; external dashboard ownership remains deployment-specific and is not an activation gate in this RFC.",
        ),
    ]
    required_item_count, completed_required_item_count = summarize_activation_items(items)
    return ObservabilityRunbookReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        runbook_ready=required_item_count == completed_required_item_count,
        required_item_count=required_item_count,
        completed_required_item_count=completed_required_item_count,
        items=items,
    )
