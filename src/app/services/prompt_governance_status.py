from __future__ import annotations

from app.config import settings
from app.contracts.prompts import PromptGovernanceStatusSummaryResponse
from app.services.governance_readiness import summarize_governance_flags
from app.services.prompt_activation_readiness import build_prompt_activation_readiness
from app.services.prompt_evidence_readiness import build_prompt_evidence_readiness
from app.services.prompt_runbook_readiness import build_prompt_runbook_readiness


def build_prompt_governance_status_summary() -> PromptGovernanceStatusSummaryResponse:
    activation_readiness = build_prompt_activation_readiness()
    runbook_readiness = build_prompt_runbook_readiness()
    evidence_readiness = build_prompt_evidence_readiness()
    governance_ready, blocking_area_count = summarize_governance_flags(
        activation_readiness.activation_ready,
        runbook_readiness.runbook_ready,
        evidence_readiness.evidence_ready,
    )
    governance_summary = [
        "Prompt technical activation remains blocked in foundation phase until live promotion, approval, and rollback controls are explicitly rolled out.",
        "Prompt operational runbook readiness remains incomplete until change approval, rollback response, and audit-evidence procedures are fully documented and approved.",
        "Prompt evidence readiness remains incomplete until regression baselines, audit traceability, and rollback-proof evidence are explicitly assembled.",
    ]
    return PromptGovernanceStatusSummaryResponse(
        service=settings.service_name,
        version=settings.service_version,
        governance_ready=governance_ready,
        activation_readiness=activation_readiness,
        runbook_readiness=runbook_readiness,
        evidence_readiness=evidence_readiness,
        blocking_area_count=blocking_area_count,
        governance_summary=governance_summary,
    )
