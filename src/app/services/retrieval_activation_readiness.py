from __future__ import annotations

from app.config import settings
from app.services.runtime_mode_config import resolve_runtime_mode_config
from app.contracts.retrieval import RetrievalActivationReadinessResponse
from app.retrieval.document_governance import build_retrieval_document_governance
from app.services.retrieval_evidence_readiness import build_retrieval_evidence_readiness
from app.services.retrieval_embedding_runtime import build_retrieval_embedding_runtime
from app.services.retrieval_ingestion_status import build_retrieval_ingestion_status
from app.services.retrieval_runbook_readiness import build_retrieval_runbook_readiness
from app.services.runtime_readiness import get_retrieval_store_runtime_status


def build_retrieval_activation_readiness() -> RetrievalActivationReadinessResponse:
    evidence_readiness = build_retrieval_evidence_readiness()
    runbook_readiness = build_retrieval_runbook_readiness()
    embedding_runtime = build_retrieval_embedding_runtime()
    ingestion_status = build_retrieval_ingestion_status()
    store_status = get_retrieval_store_runtime_status()
    document_governance = (
        None if store_status.status != "READY" else build_retrieval_document_governance()
    )

    blocking_findings: list[str] = []
    if resolve_runtime_mode_config().retrieval_mode != "enabled":
        blocking_findings.append(
            "Retrieval mode is not enabled, so the live indexed-search path is not in active rollout."
        )
    if store_status.status != "READY":
        blocking_findings.append(
            f"Retrieval store readiness is blocking live search activation: {store_status.detail}"
        )
    elif document_governance is not None and document_governance.searchable_document_count == 0:
        if document_governance.refresh_pending_document_count > 0:
            blocking_findings.append(
                "No promoted indexed documents are currently searchable because governed corpus refresh work is still in flight."
            )
        elif document_governance.withdrawn_document_count > 0:
            blocking_findings.append(
                "No promoted indexed documents are currently searchable because the latest governed corpus lineage is withdrawn."
            )
        elif document_governance.index_pending_document_count > 0:
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
    if not embedding_runtime.embedding_execution_enabled:
        blocking_findings.append(
            "Embedding provider execution is not yet enabled for broader corpus growth beyond the current bounded live-search rollout."
        )
    if not ingestion_status.live_ingestion_enabled:
        blocking_findings.append(
            "Runtime-backed ingestion execution is not yet enabled for governed corpus-change jobs."
        )

    activation_ready = (
        resolve_runtime_mode_config().retrieval_mode == "enabled"
        and store_status.status == "READY"
        and document_governance is not None
        and document_governance.searchable_document_count > 0
        and embedding_runtime.embedding_execution_enabled
        and ingestion_status.live_ingestion_enabled
        and evidence_readiness.evidence_ready
        and runbook_readiness.runbook_ready
    )

    activation_path = [
        "Review `/platform/retrieval/execution-status`, `/platform/retrieval/source-governance`, and `/platform/retrieval/document-governance` to confirm the live path and searchable corpus posture agree.",
        "Validate runtime-backed retrieval approval evidence through `/platform/retrieval/evidence-readiness` and confirm current live-search runs, not historical staged baselines, are driving the approval gate.",
        "Verify retrieval rollout, replay, rollback, and recovery procedures through `/platform/retrieval/runbook-readiness` and the service operations runbook before broader activation.",
        "Treat broader embedding-provider rollout as part of the RFC-0018 governed activation path and confirm embedding runtime posture before expanding corpus growth.",
    ]
    return RetrievalActivationReadinessResponse(
        service=settings.service_name,
        delivery_phase=settings.delivery_phase,
        retrieval_mode=resolve_runtime_mode_config().retrieval_mode,
        embedding_provider_mode=resolve_runtime_mode_config().embedding_provider_mode,
        embedding_execution_enabled=embedding_runtime.embedding_execution_enabled,
        ingestion_execution_enabled=ingestion_status.live_ingestion_enabled,
        activation_ready=activation_ready,
        blocking_findings=blocking_findings,
        activation_path=activation_path,
    )
