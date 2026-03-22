from __future__ import annotations

from app.config import settings
from app.contracts.retrieval import (
    RetrievalIndexStatus,
    RetrievalSourceDescriptor,
    RetrievalSourceGovernanceDescriptor,
    RetrievalSourceGovernanceResponse,
)
from app.retrieval.inventory_summary import summarize_retrieval_source_inventory
from app.retrieval.policy import VECTOR_STORE_STRATEGY
from app.services.retrieval_store import get_retrieval_repository


def build_retrieval_source_governance() -> RetrievalSourceGovernanceResponse:
    sources = get_retrieval_repository().list_sources()
    governance_sources = [
        _build_source_governance_descriptor(source=source)
        for source in sources
    ]
    return RetrievalSourceGovernanceResponse(
        service=settings.service_name,
        retrieval_mode=settings.retrieval_mode,
        vector_store=VECTOR_STORE_STRATEGY,
        enabled_source_count=sum(1 for source in governance_sources if source.search_enabled),
        staged_only_source_count=sum(
            1 for source in governance_sources if source.governance_status == "STAGED_ONLY"
        ),
        empty_source_count=sum(
            1 for source in governance_sources if source.governance_status == "EMPTY"
        ),
        sources=governance_sources,
    )


def _build_source_governance_descriptor(
    *, source: RetrievalSourceDescriptor
) -> RetrievalSourceGovernanceDescriptor:
    inventory = summarize_retrieval_source_inventory(source.source_id)
    governance_status, notes = _derive_source_governance(
        enabled=source.enabled,
        document_count=inventory.document_count,
        index_status=inventory.index_status,
    )
    return RetrievalSourceGovernanceDescriptor(
        source_id=source.source_id,
        kind=source.kind,
        governance_status=governance_status,
        search_enabled=source.enabled,
        document_count=inventory.document_count,
        chunk_count=inventory.chunk_count,
        index_status=inventory.index_status,
        notes=notes,
    )


def _derive_source_governance(
    *, enabled: bool, document_count: int, index_status: RetrievalIndexStatus
) -> tuple[str, str]:
    if enabled:
        return (
            "SEARCH_ENABLED",
            "Approved for bounded catalog-only retrieval during foundation phase.",
        )
    if document_count == 0:
        return (
            "EMPTY",
            "Registered as an approved source class, but no staged documents are loaded yet.",
        )
    if index_status == RetrievalIndexStatus.STAGED:
        return (
            "STAGED_ONLY",
            "Documents are staged but the source is not yet promoted into catalog-only retrieval.",
        )
    return (
        "REGISTERED_ONLY",
        "Registered in the retrieval corpus, but not yet promoted into searchable foundation scope.",
    )
