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
    corpus_change_review_ready = any(
        item.runbook_id == "retrieval_corpus_change_review" and item.status == "READY"
        for item in runbook_readiness.items
    ) and any(
        item.evidence_id == "retrieval_corpus_change_evidence_pack" and item.status == "READY"
        for item in evidence_readiness.items
    )
    governance_ready, blocking_area_count = summarize_governance_flags(
        activation_readiness.activation_ready,
        runbook_readiness.runbook_ready,
        evidence_readiness.evidence_ready,
    )
    governance_summary = [
        "Retrieval technical activation now includes a live indexed search path plus bounded live embedding dependency posture, but broader rollout remains blocked until governance gates are completed.",
        "Retrieval operational runbook readiness now includes explicit corpus-change and artifact-backed incident review, but named on-call escalation is still not approved.",
        (
            "Retrieval evidence readiness now includes a runtime-backed approval gate summary derived "
            f"from governed retrieval evaluation runs, currently reporting '{evidence_readiness.approval_gate.evidence_state.value}'."
        ),
    ]
    if not corpus_change_review_ready:
        governance_summary.append(
            "Corpus-change review is not yet fully evidenced through bounded ingestion diagnostics."
        )
    return RetrievalGovernanceStatusResponse(
        service=settings.service_name,
        delivery_phase=settings.delivery_phase,
        governance_ready=governance_ready,
        activation_readiness=activation_readiness,
        runbook_readiness=runbook_readiness,
        evidence_readiness=evidence_readiness,
        corpus_change_review_ready=corpus_change_review_ready,
        blocking_area_count=blocking_area_count,
        governance_summary=governance_summary,
    )
