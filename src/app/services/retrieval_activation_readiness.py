from __future__ import annotations

from app.config import settings
from app.contracts.retrieval import RetrievalActivationReadinessResponse
from app.retrieval.document_governance import build_retrieval_document_governance
from app.services.retrieval_evidence_readiness import build_retrieval_evidence_readiness
from app.services.retrieval_runbook_readiness import build_retrieval_runbook_readiness
from app.services.runtime_readiness import get_retrieval_store_runtime_status


def build_retrieval_activation_readiness() -> RetrievalActivationReadinessResponse:
    evidence_readiness = build_retrieval_evidence_readiness()
    runbook_readiness = build_retrieval_runbook_readiness()
    store_status = get_retrieval_store_runtime_status()
    document_governance = (
        None if store_status.status != "READY" else build_retrieval_document_governance()
    )

    blocking_findings: list[str] = []
    if settings.retrieval_mode != "enabled":
        blocking_findings.append(
            "Retrieval mode is not enabled, so the live indexed-search path is not in active rollout."
        )
    if store_status.status != "READY":
        blocking_findings.append(
            f"Retrieval store readiness is blocking live search activation: {store_status.detail}"
        )
    elif document_governance is not None and document_governance.searchable_document_count == 0:
        if document_governance.index_pending_document_count > 0:
            blocking_findings.append(
                "No promoted indexed documents are currently searchable because indexing is still pending for the governed corpus."
            )
        elif document_governance.blocked_document_count > 0:
            blocking_findings.append(
                "No promoted indexed documents are currently searchable because the governed corpus is blocked or rolled back."
            )
        else:
            blocking_findings.append(
                "No promoted indexed documents are currently registered for the live retrieval path."
            )
    if not evidence_readiness.evidence_ready:
        blocking_findings.append(
            "Retrieval evidence readiness is still incomplete; runtime-backed live-search evidence exists, but reindex and rollback evidence remains outstanding."
        )
    if not runbook_readiness.runbook_ready:
        blocking_findings.append(
            "Retrieval runbook readiness remains incomplete; formal on-call escalation posture is not yet approved."
        )
    if settings.embedding_provider_mode != "enabled":
        blocking_findings.append(
            "Embedding provider execution is still disabled for broader corpus growth beyond the current bounded live-search rollout."
        )

    activation_ready = (
        settings.retrieval_mode == "enabled"
        and store_status.status == "READY"
        and document_governance is not None
        and document_governance.searchable_document_count > 0
        and evidence_readiness.evidence_ready
        and runbook_readiness.runbook_ready
    )

    activation_path = [
        "Review `/platform/retrieval/execution-status`, `/platform/retrieval/source-governance`, and `/platform/retrieval/document-governance` to confirm the live path and searchable corpus posture agree.",
        "Validate runtime-backed retrieval approval evidence through `/platform/retrieval/evidence-readiness` and confirm current live-search runs, not historical staged baselines, are driving the approval gate.",
        "Verify retrieval rollout, replay, rollback, and recovery procedures through `/platform/retrieval/runbook-readiness` and the service operations runbook before broader activation.",
        "Treat broader embedding-provider rollout as separate follow-on work after the bounded live-search path is fully governed.",
    ]
    return RetrievalActivationReadinessResponse(
        service=settings.service_name,
        delivery_phase=settings.delivery_phase,
        retrieval_mode=settings.retrieval_mode,
        embedding_provider_mode=settings.embedding_provider_mode,
        activation_ready=activation_ready,
        blocking_findings=blocking_findings,
        activation_path=activation_path,
    )
