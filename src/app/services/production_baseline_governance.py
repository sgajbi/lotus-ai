from __future__ import annotations

from app.config import settings
from app.contracts.production_baseline import (
    ProductionBaselineGovernanceStatusResponse,
)
from app.services.governance_readiness import summarize_governance_flags
from app.services.production_baseline_activation_readiness import (
    build_production_baseline_activation_readiness,
)
from app.services.production_baseline_runbook_readiness import (
    build_production_baseline_runbook_readiness,
)
from app.services.production_baseline_runtime import build_production_baseline_runtime_status


def build_production_baseline_governance_status(
    app_state: object | None = None,
) -> ProductionBaselineGovernanceStatusResponse:
    runtime_status = build_production_baseline_runtime_status(app_state)
    activation_readiness = build_production_baseline_activation_readiness(app_state)
    runbook_readiness = build_production_baseline_runbook_readiness()
    governance_ready, blocking_area_count = summarize_governance_flags(
        activation_readiness.activation_ready,
        runbook_readiness.runbook_ready,
    )
    return ProductionBaselineGovernanceStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        governance_ready=governance_ready,
        runtime_status=runtime_status,
        activation_readiness=activation_readiness,
        runbook_readiness=runbook_readiness,
        blocking_area_count=blocking_area_count,
        governance_summary=[
            runtime_status.status_summary[0],
            (
                "Production activation readiness is satisfied because all required baseline dependencies are production-standard."
                if activation_readiness.activation_ready
                else "Production activation readiness remains blocked until all required baseline dependencies move from fallback or blocked to production-standard."
            ),
            (
                "Production runbook readiness is complete and operator guidance now separates local demo setup from accepted go-live posture."
                if runbook_readiness.runbook_ready
                else "Production runbook readiness remains incomplete for at least one required operational path."
            ),
        ],
    )
