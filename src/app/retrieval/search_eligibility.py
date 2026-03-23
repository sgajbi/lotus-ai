from __future__ import annotations

from dataclasses import dataclass

from app.contracts.retrieval import (
    RetrievalChunkDescriptor,
    RetrievalDocumentDescriptor,
    RetrievalIndexStatus,
    RetrievalSourceDescriptor,
)


@dataclass(frozen=True)
class RetrievalDocumentEligibility:
    governance_status: str
    search_enabled: bool
    notes: str


def build_document_eligibility(
    *, source: RetrievalSourceDescriptor, document: RetrievalDocumentDescriptor
) -> RetrievalDocumentEligibility:
    if source.enabled and document.index_status == RetrievalIndexStatus.INDEXED:
        return RetrievalDocumentEligibility(
            governance_status="SEARCH_ENABLED",
            search_enabled=True,
            notes="Document is promoted through an enabled source and is fully indexed for live search.",
        )
    if source.enabled:
        return RetrievalDocumentEligibility(
            governance_status="INDEX_PENDING",
            search_enabled=False,
            notes="Source is enabled, but the document is not fully indexed yet and cannot enter live search.",
        )
    return RetrievalDocumentEligibility(
        governance_status="BLOCKED_BY_SOURCE",
        search_enabled=False,
        notes="Document remains blocked from live search because its source is not enabled.",
    )


def is_live_search_chunk_eligible(
    *,
    source: RetrievalSourceDescriptor,
    document: RetrievalDocumentDescriptor,
    chunk: RetrievalChunkDescriptor,
) -> bool:
    document_eligibility = build_document_eligibility(source=source, document=document)
    return (
        document_eligibility.search_enabled and chunk.index_status == RetrievalIndexStatus.INDEXED
    )
