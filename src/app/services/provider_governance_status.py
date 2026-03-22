from __future__ import annotations

from app.config import settings
from app.contracts.providers import ProviderGovernanceStatusResponse
from app.services.governance_readiness import summarize_governance_flags
from app.services.provider_activation_readiness import build_provider_activation_readiness
from app.services.provider_evidence_readiness import build_provider_evidence_readiness
from app.services.provider_runbook_readiness import build_provider_runbook_readiness


def build_provider_governance_status() -> ProviderGovernanceStatusResponse:
    activation_readiness = build_provider_activation_readiness()
    runbook_readiness = build_provider_runbook_readiness()
    evidence_readiness = build_provider_evidence_readiness()
    governance_ready, blocking_area_count = summarize_governance_flags(
        activation_readiness.activation_ready,
        runbook_readiness.runbook_ready,
        evidence_readiness.evidence_ready,
    )
    governance_summary = [
        "Provider technical activation remains blocked in foundation phase until allowlisted live execution modes and controls are explicitly rolled out.",
        "Provider operational runbook readiness remains incomplete until escalation, rate-limit, and observability procedures are fully documented and approved.",
        "Provider evidence readiness now includes staged runtime and failure-mode fixtures plus a recorded regression baseline, but live audit traceability and failover-proof evidence still block activation.",
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
