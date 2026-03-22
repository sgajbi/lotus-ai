from __future__ import annotations

from app.config import settings
from app.contracts.async_runtime import AsyncGovernanceStatusResponse
from app.services.async_activation_readiness_service import build_async_activation_readiness
from app.services.async_runbook_readiness_service import build_async_runbook_readiness


def build_async_governance_status() -> AsyncGovernanceStatusResponse:
    activation_readiness = build_async_activation_readiness()
    runbook_readiness = build_async_runbook_readiness()
    governance_ready = activation_readiness.activation_ready and runbook_readiness.runbook_ready
    blocking_area_count = int(not activation_readiness.activation_ready) + int(
        not runbook_readiness.runbook_ready
    )
    governance_summary = [
        "Async technical activation remains blocked in foundation phase until queue, worker, and job enablement posture are explicitly rolled out.",
        "Async operational runbook readiness remains incomplete until on-call, replay, and observability procedures are fully documented and approved.",
    ]
    return AsyncGovernanceStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        governance_ready=governance_ready,
        activation_readiness=activation_readiness,
        runbook_readiness=runbook_readiness,
        blocking_area_count=blocking_area_count,
        governance_summary=governance_summary,
    )
