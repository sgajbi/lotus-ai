from __future__ import annotations

from app.config import settings
from app.contracts.safety import SafetyGovernanceStatusResponse
from app.services.governance_readiness import summarize_governance_flags
from app.services.safety_evidence_readiness import build_safety_evidence_readiness
from app.services.safety_runbook_readiness import build_safety_runbook_readiness
from app.services.safety_status import build_safety_runtime_status


def build_safety_governance_status() -> SafetyGovernanceStatusResponse:
    runtime_status = build_safety_runtime_status()
    runbook_readiness = build_safety_runbook_readiness()
    evidence_readiness = build_safety_evidence_readiness()
    governance_ready, blocking_area_count = summarize_governance_flags(
        runtime_status.runtime_redaction_active,
        runbook_readiness.runbook_ready,
        evidence_readiness.evidence_ready,
    )
    governance_summary = [
        (
            "Safety runtime enforcement is currently active for bounded outputs."
            if runtime_status.runtime_redaction_active
            else "Safety runtime enforcement is not yet active; documented-only posture remains explicit."
        ),
        (
            "Safety runbook readiness is grounded in documented activation, rollback, degraded-response, "
            "and audit-review procedures, but named on-call ownership and dedicated observability remain incomplete."
        ),
        (
            "Safety evidence readiness now uses a runtime-backed approval gate summary derived from governed safety evaluation runs, "
            f"currently reporting '{evidence_readiness.approval_gate.evidence_state.value}'."
        ),
    ]
    return SafetyGovernanceStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        governance_ready=governance_ready,
        runtime_status=runtime_status,
        runbook_readiness=runbook_readiness,
        evidence_readiness=evidence_readiness,
        blocking_area_count=blocking_area_count,
        governance_summary=governance_summary,
    )
