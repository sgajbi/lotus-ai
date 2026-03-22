from __future__ import annotations

from app.config import settings
from app.contracts.providers import ProviderGovernanceStatusResponse
from app.services.provider_activation_readiness import build_provider_activation_readiness
from app.services.provider_evidence_readiness import build_provider_evidence_readiness
from app.services.provider_runbook_readiness import build_provider_runbook_readiness


def build_provider_governance_status() -> ProviderGovernanceStatusResponse:
    activation_readiness = build_provider_activation_readiness()
    runbook_readiness = build_provider_runbook_readiness()
    evidence_readiness = build_provider_evidence_readiness()
    governance_ready = (
        activation_readiness.activation_ready
        and runbook_readiness.runbook_ready
        and evidence_readiness.evidence_ready
    )
    blocking_area_count = (
        int(not activation_readiness.activation_ready)
        + int(not runbook_readiness.runbook_ready)
        + int(not evidence_readiness.evidence_ready)
    )
    governance_summary = [
        "Provider technical activation remains blocked in foundation phase until allowlisted live execution modes and controls are explicitly rolled out.",
        "Provider operational runbook readiness remains incomplete until escalation, rate-limit, and observability procedures are fully documented and approved.",
        "Provider evidence readiness remains incomplete until regression baselines, audit traceability, and failover-proof evidence are explicitly assembled.",
    ]
    return ProviderGovernanceStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        governance_ready=governance_ready,
        activation_readiness=activation_readiness,
        runbook_readiness=runbook_readiness,
        evidence_readiness=evidence_readiness,
        blocking_area_count=blocking_area_count,
        governance_summary=governance_summary,
    )
