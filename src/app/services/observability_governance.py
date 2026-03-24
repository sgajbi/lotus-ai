from __future__ import annotations

from app.config import settings
from app.contracts.observability import ObservabilityGovernanceStatusResponse
from app.services.governance_readiness import summarize_governance_flags
from app.services.observability_activation_readiness import build_observability_activation_readiness
from app.services.observability_runbook_readiness import build_observability_runbook_readiness
from app.services.observability_runtime import build_observability_runtime_status


def build_observability_governance_status() -> ObservabilityGovernanceStatusResponse:
    runtime_status = build_observability_runtime_status()
    activation_readiness = build_observability_activation_readiness()
    runbook_readiness = build_observability_runbook_readiness()
    governance_ready, blocking_area_count = summarize_governance_flags(
        activation_readiness.activation_ready,
        runbook_readiness.runbook_ready,
    )
    return ObservabilityGovernanceStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        governance_ready=governance_ready,
        runtime_status=runtime_status,
        activation_readiness=activation_readiness,
        runbook_readiness=runbook_readiness,
        blocking_area_count=blocking_area_count,
        governance_summary=[
            "Observability now exposes bounded runtime, incident-summary, and caller, tenant, and capability breakdown surfaces through one in-service API family.",
            (
                "Activation readiness is satisfied because all governed domains expose incident evidence and the supporting audit and caller-policy stores are SQL-backed."
                if activation_readiness.activation_ready
                else "Activation readiness remains blocked until the supporting audit and caller-policy stores are SQL-backed and restart-safe."
            ),
            (
                "Runbook readiness is complete for runtime review, incident review, and authorization-aware breakdown inspection."
                if runbook_readiness.runbook_ready
                else "Runbook readiness is incomplete for at least one required observability operator path."
            ),
        ],
    )
