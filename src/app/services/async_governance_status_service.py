from __future__ import annotations

from app.config import settings
from app.contracts.async_runtime import AsyncCutoverState
from app.contracts.async_runtime import AsyncGovernanceStatusResponse
from app.services.async_operational_state import build_async_operational_state
from app.services.governance_readiness import summarize_governance_flags
from app.services.async_activation_readiness_service import build_async_activation_readiness
from app.services.readiness_catalog import build_async_runbook_readiness


def build_async_governance_status() -> AsyncGovernanceStatusResponse:
    activation_readiness = build_async_activation_readiness()
    runbook_readiness = build_async_runbook_readiness()
    operational_state = build_async_operational_state()
    governance_ready, blocking_area_count = summarize_governance_flags(
        activation_readiness.activation_ready,
        runbook_readiness.runbook_ready,
    )
    if activation_readiness.cutover_state == AsyncCutoverState.DEDICATED_WORKERS_ACTIVE:
        governance_summary = [
            "Async dedicated workers are now the active primary path for the allowlisted retrieval-indexing and evaluation-execution job types, while the service database remains authoritative async truth.",
            *operational_state.degraded_findings,
            "Async technical rollout is now converged on the dedicated-worker cutover model, but governance remains blocked until named on-call ownership is approved.",
        ]
    elif activation_readiness.cutover_state == AsyncCutoverState.DEGRADED_FALLBACK:
        governance_summary = [
            "Async worker rollout is currently in an explicit degraded fallback posture; queue-backed worker execution is not healthy enough to treat as stable primary execution.",
            *operational_state.degraded_findings,
            "Async technical rollout is now converged on the dedicated-worker cutover model, but governance remains blocked until named on-call ownership is approved.",
        ]
    elif activation_readiness.cutover_state == AsyncCutoverState.QUEUE_DELIVERY_SHADOW:
        governance_summary = [
            "Async rollout is currently in queue-delivery shadow mode: managed queue delivery is wired, but dedicated workers are not yet the active primary execution path.",
            "Async technical rollout is now converged on the dedicated-worker cutover model, but governance remains blocked until named on-call ownership is approved.",
        ]
    else:
        governance_summary = [
            "Async technical activation remains partially blocked in foundation phase: durable submission, worker claim, lease recovery, retrieval-indexing execution, and evaluation execution are active for a narrow allowlist, but dedicated worker fleet rollout and broader job enablement are still gated.",
            "Async technical rollout is now converged on the dedicated-worker cutover model, but governance remains blocked until named on-call ownership is approved.",
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
