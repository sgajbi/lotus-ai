from __future__ import annotations

from app.config import settings
from app.contracts.retrieval import RetrievalActivationReadinessResponse


def build_retrieval_activation_readiness() -> RetrievalActivationReadinessResponse:
    blocking_findings = [
        "Live retrieval search remains disabled in the current foundation phase even though runtime-backed indexing is now available.",
        "Embedding provider execution is not enabled for live retrieval indexing.",
        "No governed live vector indexing and search backend has been approved for production execution.",
        "Retrieval remains in partial rollout mode until search activation and broader rollout gates are completed.",
    ]
    activation_path = [
        "Approve a governed live retrieval rollout with explicit vector indexing and search backend controls.",
        "Enable embedding provider execution and retrieval execution through a reviewed rollout slice.",
        "Complete retrieval-specific safety, provenance, and operational controls for live search and indexing.",
        "Validate end-to-end retrieval behavior with evaluation evidence and runtime supportability checks before activation.",
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
