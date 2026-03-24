from __future__ import annotations

from app.config import settings
from app.contracts.production_baseline import (
    ProductionBaselineRunbookReadinessItem,
    ProductionBaselineRunbookReadinessResponse,
)
from app.services.governance_readiness import summarize_activation_items


def build_production_baseline_runbook_readiness() -> (
    ProductionBaselineRunbookReadinessResponse
):
    items = [
        ProductionBaselineRunbookReadinessItem(
            runbook_id="deployment_baseline_boundary",
            status="READY",
            required_for_activation=True,
            notes="Operator guidance now distinguishes local or demo-capable posture, prod-shaped local posture, and the accepted production-ready baseline explicitly.",
        ),
        ProductionBaselineRunbookReadinessItem(
            runbook_id="migration_and_startup_procedure",
            status="READY",
            required_for_activation=True,
            notes="Container startup and release behavior document that migrations must be applied before the runtime is treated as ready.",
        ),
        ProductionBaselineRunbookReadinessItem(
            runbook_id="queue_and_worker_operations",
            status="READY",
            required_for_activation=True,
            notes="Dedicated worker, Redis queue, backlog, drain, and degraded async posture are documented as part of the accepted deployment baseline.",
        ),
        ProductionBaselineRunbookReadinessItem(
            runbook_id="artifact_and_object_store_posture",
            status="READY",
            required_for_activation=True,
            notes="Operator guidance explains that filesystem or memory-backed artifact payload storage is local fallback only and not acceptable for the production baseline.",
        ),
        ProductionBaselineRunbookReadinessItem(
            runbook_id="secret_injection_boundary",
            status="READY",
            required_for_activation=True,
            notes="Runbooks and deployment docs now state explicitly that local env-file secret handling is non-production and that deployment-managed secret injection is required for go-live posture.",
        ),
    ]
    required_item_count, completed_required_item_count = summarize_activation_items(items)
    return ProductionBaselineRunbookReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        runbook_ready=required_item_count == completed_required_item_count,
        required_item_count=required_item_count,
        completed_required_item_count=completed_required_item_count,
        items=items,
    )
