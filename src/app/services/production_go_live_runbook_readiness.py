from __future__ import annotations

from app.config import settings
from app.contracts.production_go_live import (
    ProductionGoLiveRunbookReadinessItem,
    ProductionGoLiveRunbookReadinessResponse,
)
from app.services.governance_readiness import summarize_activation_items
from app.services.provider_runbook_readiness import build_provider_runbook_readiness


def build_production_go_live_runbook_readiness() -> ProductionGoLiveRunbookReadinessResponse:
    provider_runbook = build_provider_runbook_readiness()
    items = [
        ProductionGoLiveRunbookReadinessItem(
            runbook_id="production_go_live_platform_review",
            status="READY",
            required_for_activation=True,
            notes=(
                "Production go-live review now distinguishes technically running, production-capable, and production-approved posture through dedicated platform endpoints."
            ),
        ),
        ProductionGoLiveRunbookReadinessItem(
            runbook_id="production_go_live_managed_infrastructure_boundary",
            status="READY",
            required_for_activation=True,
            notes=(
                "Managed-secret and managed object-storage approval boundaries are now documented as explicit production go-live prerequisites instead of deployment recommendations."
            ),
        ),
        ProductionGoLiveRunbookReadinessItem(
            runbook_id="production_go_live_provider_freeze_and_rollback",
            status="READY",
            required_for_activation=True,
            notes=(
                "Provider freeze posture now maps to `ALLOWLISTED_DISABLED`, and rollback guidance explicitly treats that bounded rollout state as the first production-safe target."
            ),
        ),
        ProductionGoLiveRunbookReadinessItem(
            runbook_id="production_go_live_provider_incident_alignment",
            status="READY" if provider_runbook.runbook_ready else "NOT_READY",
            required_for_activation=True,
            notes=(
                "Provider incident, escalation, spend-anomaly, degradation, and recovery runbooks must also be complete before production go-live can be treated as fully approved."
            ),
        ),
    ]
    required_item_count, completed_required_item_count = summarize_activation_items(items)
    return ProductionGoLiveRunbookReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        runbook_ready=completed_required_item_count == required_item_count,
        required_item_count=required_item_count,
        completed_required_item_count=completed_required_item_count,
        items=items,
        go_live_checklist=[
            "Confirm `/platform/production-go-live/runtime-status` reports platform production approval and the intended provider freeze or rollback posture.",
            "Confirm `/platform/production-go-live/activation-readiness` shows no remaining platform or provider blockers.",
            "Confirm `/platform/production-go-live/use-case-approval` distinguishes limited-rollout readiness from active-production approval for the named downstream path.",
            "Confirm `/platform/production-go-live/governance-status` and the embedded `production_go_live_governance` platform block match the detailed views before exposing real production traffic.",
        ],
    )
