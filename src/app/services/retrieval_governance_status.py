from __future__ import annotations

from app.config import settings
from app.contracts.retrieval import RetrievalGovernanceStatusResponse
from app.services.governance_readiness import summarize_governance_flags
from app.services.retrieval_activation_readiness import build_retrieval_activation_readiness
from app.services.retrieval_evidence_readiness import build_retrieval_evidence_readiness
from app.services.retrieval_runbook_readiness import build_retrieval_runbook_readiness


def build_retrieval_governance_status() -> RetrievalGovernanceStatusResponse:
    activation_readiness = build_retrieval_activation_readiness()
    runbook_readiness = build_retrieval_runbook_readiness()
    evidence_readiness = build_retrieval_evidence_readiness()
    governance_ready, blocking_area_count = summarize_governance_flags(
        activation_readiness.activation_ready,
        runbook_readiness.runbook_ready,
        evidence_readiness.evidence_ready,
    )
    governance_summary = [
        "Retrieval technical activation remains blocked in foundation phase until live indexing, search, and embedding controls are explicitly rolled out.",
        "Retrieval operational runbook readiness remains incomplete until reindex, replay, and observability procedures are fully documented and approved.",
        "Retrieval evidence readiness remains incomplete until regression baselines, citation traceability, and rollback-proof evidence are explicitly assembled.",
    ]
    return RetrievalGovernanceStatusResponse(
        service=settings.service_name,
        delivery_phase=settings.delivery_phase,
        governance_ready=governance_ready,
        activation_readiness=activation_readiness,
        runbook_readiness=runbook_readiness,
        evidence_readiness=evidence_readiness,
        blocking_area_count=blocking_area_count,
        governance_summary=governance_summary,
    )
