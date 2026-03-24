from __future__ import annotations

from app.config import settings
from app.contracts.retrieval import (
    RetrievalEvidenceReadinessItem,
    RetrievalEvidenceReadinessResponse,
)
from app.contracts.runtime_readiness import RuntimeReadinessStatus
from app.services.artifact_runtime import ACTIVE_ARTIFACT_DOMAINS, build_artifact_runtime_status
from app.services.eval_approval_gate_summary import build_retrieval_approval_gate_summary
from app.services.governance_readiness import summarize_activation_items
from app.services.retrieval_ingestion_artifacts import load_retrieval_ingestion_artifact_refs
from app.services.retrieval_store import get_retrieval_repository
from app.services.runtime_readiness import get_retrieval_store_runtime_status


def build_retrieval_evidence_readiness() -> RetrievalEvidenceReadinessResponse:
    approval_gate = build_retrieval_approval_gate_summary()
    runtime_backed_live_evidence_present = approval_gate.runtime_backed_fixture_count > 0
    artifact_runtime = build_artifact_runtime_status()
    artifact_review_ready = (
        artifact_runtime.metadata_store.status is RuntimeReadinessStatus.READY
        and artifact_runtime.object_store.status is RuntimeReadinessStatus.READY
        and "retrieval" in ACTIVE_ARTIFACT_DOMAINS
    )
    retrieval_store_ready = (
        get_retrieval_store_runtime_status().status is RuntimeReadinessStatus.READY
    )
    corpus_change_evidence_present = (
        artifact_review_ready
        and retrieval_store_ready
        and any(
            load_retrieval_ingestion_artifact_refs(job_id=job.job_id)
            for job in get_retrieval_repository().list_ingestion_jobs()
        )
    )
    items = [
        RetrievalEvidenceReadinessItem(
            evidence_id="retrieval_fixture_coverage_pack",
            status="READY" if runtime_backed_live_evidence_present else "FOUNDATION_STAGED",
            required_for_activation=True,
            notes=(
                "Runtime-backed retrieval fixtures now validate live retrieval behavior."
                if runtime_backed_live_evidence_present
                else (
                    "Foundation-phase retrieval fixtures exist, but a retrieval-specific live "
                    "activation evidence pack is not yet approved."
                )
            ),
        ),
        RetrievalEvidenceReadinessItem(
            evidence_id="retrieval_regression_run_baseline",
            status="READY" if runtime_backed_live_evidence_present else "NOT_READY",
            required_for_activation=True,
            notes=(
                "A governed runtime-backed regression baseline now exists for live retrieval search behavior."
                if runtime_backed_live_evidence_present
                else (
                    "A governed regression-run baseline proving retrieval search, citation, and "
                    "refusal behavior for rollout candidates is not yet recorded."
                )
            ),
        ),
        RetrievalEvidenceReadinessItem(
            evidence_id="retrieval_citation_traceability_pack",
            status="READY" if runtime_backed_live_evidence_present else "NOT_READY",
            required_for_activation=True,
            notes=(
                "Runtime-backed retrieval tasks now preserve live execution stage plus citation traceability evidence."
                if runtime_backed_live_evidence_present
                else (
                    "Activation review evidence linking indexed sources, citations, and runtime "
                    "search traces is not yet assembled."
                )
            ),
        ),
        RetrievalEvidenceReadinessItem(
            evidence_id="retrieval_embedding_runtime_pack",
            status="READY" if runtime_backed_live_evidence_present else "NOT_READY",
            required_for_activation=True,
            notes=(
                "Runtime-backed retrieval evidence now includes embedding provider posture for indexing and live-search dependency review."
                if runtime_backed_live_evidence_present
                else (
                    "Activation review evidence linking retrieval indexing posture to embedding-provider runtime is not yet assembled."
                )
            ),
        ),
        RetrievalEvidenceReadinessItem(
            evidence_id="retrieval_reindex_and_rollback_evidence_pack",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "Reindex, rollback, and corpus-recovery evidence proving safe reversion behavior "
                "is not yet documented."
            ),
        ),
        RetrievalEvidenceReadinessItem(
            evidence_id="retrieval_corpus_change_evidence_pack",
            status="READY" if corpus_change_evidence_present else "NOT_READY",
            required_for_activation=True,
            notes=(
                "Runtime-backed corpus-change evidence now includes artifact-backed ingestion diagnostics plus search-eligibility convergence review."
                if corpus_change_evidence_present
                else (
                    "Runtime-backed corpus-change evidence remains blocked until durable retrieval ingestion state is readable through the active retrieval store."
                    if not retrieval_store_ready
                    else (
                        "Runtime-backed corpus-change evidence remains blocked until the governed artifact backbone is operational for retrieval and bounded ingestion diagnostics have been recorded."
                        if not artifact_review_ready
                        else (
                            "Runtime-backed evidence covering document refresh, withdrawal, and search-eligibility convergence is not yet assembled."
                        )
                    )
                )
            ),
        ),
    ]
    required_item_count, completed_required_item_count = summarize_activation_items(items)
    evidence_ready = completed_required_item_count == required_item_count
    return RetrievalEvidenceReadinessResponse(
        service=settings.service_name,
        delivery_phase=settings.delivery_phase,
        evidence_ready=evidence_ready,
        required_item_count=required_item_count,
        completed_required_item_count=completed_required_item_count,
        items=items,
        approval_gate=approval_gate,
    )
