from __future__ import annotations

from dataclasses import dataclass

from app.contracts.retrieval import RetrievalExecutionRequest, RetrievalSearchHit
from app.repositories.retrieval_repository import RetrievalRepository


@dataclass(frozen=True)
class IndexedRetrievalSearchResult:
    indexed_chunks_available: bool
    hits: list[RetrievalSearchHit]


def search_indexed_chunks(
    *,
    repository: RetrievalRepository,
    request: RetrievalExecutionRequest,
) -> IndexedRetrievalSearchResult:
    if not repository.has_searchable_indexed_chunks(request.source_ids):
        return IndexedRetrievalSearchResult(indexed_chunks_available=False, hits=[])
    return IndexedRetrievalSearchResult(
        indexed_chunks_available=True,
        hits=repository.search_indexed_hits(request),
    )
