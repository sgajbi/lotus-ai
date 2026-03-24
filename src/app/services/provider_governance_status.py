from __future__ import annotations

from app.config import settings
from app.contracts.providers import ProviderGovernanceStatusResponse
from app.services.governance_readiness import summarize_governance_flags
from app.services.provider_activation_readiness import build_provider_activation_readiness
from app.services.provider_evidence_readiness import build_provider_evidence_readiness
from app.services.provider_expansion_policy import build_provider_expansion_policy
from app.services.provider_runbook_readiness import build_provider_runbook_readiness


def build_provider_governance_status() -> ProviderGovernanceStatusResponse:
    activation_readiness = build_provider_activation_readiness()
    runbook_readiness = build_provider_runbook_readiness()
    evidence_readiness = build_provider_evidence_readiness()
    expansion_policy = build_provider_expansion_policy()
    governance_ready, blocking_area_count = summarize_governance_flags(
        activation_readiness.activation_ready,
        runbook_readiness.runbook_ready,
        evidence_readiness.evidence_ready,
        not expansion_policy.expansion_blocked,
    )
    governance_summary = [
        "Provider technical activation now includes bounded live embedding execution, but broader provider rollout remains blocked until both text and embedding control gates are explicitly approved together.",
        "Provider operational runbook readiness remains incomplete until escalation, spend-anomaly, and degradation-response procedures are fully documented and approved.",
        (
            "Provider evidence readiness now includes a runtime-backed approval gate summary derived "
            f"from governed provider evaluation runs, currently reporting '{evidence_readiness.approval_gate.evidence_state.value}'."
        ),
    ]
    if expansion_policy.expansion_blocked:
        governance_summary.append(
            "Provider expansion posture is currently blocked because registered provider breadth has exhausted or exceeded the bounded slot model for at least one capability."
        )
    return ProviderGovernanceStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        governance_ready=governance_ready,
        activation_readiness=activation_readiness,
        runbook_readiness=runbook_readiness,
        evidence_readiness=evidence_readiness,
        expansion_policy=expansion_policy,
        blocking_area_count=blocking_area_count,
        governance_summary=governance_summary,
    )
