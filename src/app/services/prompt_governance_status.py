from __future__ import annotations

from app.config import settings
from app.contracts.prompts import PromptGovernanceStatusSummaryResponse
from app.services.prompt_activation_readiness import build_prompt_activation_readiness
from app.services.prompt_runbook_readiness import build_prompt_runbook_readiness


def build_prompt_governance_status_summary() -> PromptGovernanceStatusSummaryResponse:
    activation_readiness = build_prompt_activation_readiness()
    runbook_readiness = build_prompt_runbook_readiness()
    governance_ready = activation_readiness.activation_ready and runbook_readiness.runbook_ready
    blocking_area_count = int(not activation_readiness.activation_ready) + int(
        not runbook_readiness.runbook_ready
    )
    governance_summary = [
        "Prompt technical activation remains blocked in foundation phase until live promotion, approval, and rollback controls are explicitly rolled out.",
        "Prompt operational runbook readiness remains incomplete until change approval, rollback response, and audit-evidence procedures are fully documented and approved.",
    ]
    return PromptGovernanceStatusSummaryResponse(
        service=settings.service_name,
        version=settings.service_version,
        governance_ready=governance_ready,
        activation_readiness=activation_readiness,
        runbook_readiness=runbook_readiness,
        blocking_area_count=blocking_area_count,
        governance_summary=governance_summary,
    )
