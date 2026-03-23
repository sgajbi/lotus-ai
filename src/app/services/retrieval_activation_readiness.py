from __future__ import annotations

from app.config import settings
from app.contracts.retrieval import RetrievalActivationReadinessResponse


def build_retrieval_activation_readiness() -> RetrievalActivationReadinessResponse:
    blocking_findings = [
        "Live retrieval search capability exists, but governed rollout remains incomplete.",
        "Embedding provider execution is not enabled for broader live retrieval indexing growth.",
        "Retrieval evaluation, runbook, and governance gates are not yet sufficient for full activation.",
        "Retrieval remains in partial rollout mode until live-search rollout controls are completed.",
    ]
    activation_path = [
        "Approve the governed live retrieval rollout with explicit indexed-search controls.",
        "Complete retrieval-specific safety, provenance, and operational controls for live search.",
        "Validate end-to-end retrieval behavior with runtime-backed evaluation evidence.",
        "Complete retrieval rollout and rollback supportability checks before broader activation.",
    ]
    return RetrievalActivationReadinessResponse(
        service=settings.service_name,
        delivery_phase=settings.delivery_phase,
        retrieval_mode=settings.retrieval_mode,
        embedding_provider_mode=settings.embedding_provider_mode,
        activation_ready=False,
        blocking_findings=blocking_findings,
        activation_path=activation_path,
    )
