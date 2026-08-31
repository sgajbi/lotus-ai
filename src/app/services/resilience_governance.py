from __future__ import annotations

from app.config import settings
from app.contracts.resilience import ResilienceGovernanceStatusResponse
from app.services.governance_readiness import summarize_governance_flags
from app.services.resilience_activation_readiness import build_resilience_activation_readiness
from app.services.resilience_drill_evidence import build_resilience_drill_evidence
from app.services.resilience_restore_plan import build_resilience_restore_plan
from app.services.readiness_catalog import build_resilience_runbook_readiness
from app.services.resilience_runtime import build_resilience_runtime_status


def build_resilience_governance_status() -> ResilienceGovernanceStatusResponse:
    runtime_status = build_resilience_runtime_status()
    restore_plan = build_resilience_restore_plan()
    drill_evidence = build_resilience_drill_evidence()
    activation_readiness = build_resilience_activation_readiness()
    runbook_readiness = build_resilience_runbook_readiness()
    governance_ready, blocking_area_count = summarize_governance_flags(
        activation_readiness.activation_ready,
        runbook_readiness.runbook_ready,
        drill_evidence.drill_evidence_ready,
    )
    return ResilienceGovernanceStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        governance_ready=governance_ready,
        runtime_status=runtime_status,
        restore_plan=restore_plan,
        drill_evidence=drill_evidence,
        activation_readiness=activation_readiness,
        runbook_readiness=runbook_readiness,
        blocking_area_count=blocking_area_count,
        governance_summary=[
            runtime_status.status_summary[0],
            (
                "Resilience activation readiness is satisfied because continuity is no longer relying on local or degraded fallback posture and required drill evidence is current."
                if activation_readiness.activation_ready
                else "Resilience activation readiness remains blocked until degraded or fallback continuity posture and drill-evidence gaps are resolved."
            ),
            (
                "Resilience runbook readiness is complete for restore ordering, queue and worker recovery, provider and retrieval validation, and drill review boundaries."
                if runbook_readiness.runbook_ready
                else "Resilience runbook readiness remains incomplete for at least one required recovery-review path."
            ),
            (
                "Required resilience drill evidence is current, so governance can treat the recovery model as drill-verified rather than only documented."
                if drill_evidence.drill_evidence_ready
                else "Required resilience drill evidence is still partial or staged-only, so governance must not treat the recovery model as drill-verified yet."
            ),
        ],
    )
