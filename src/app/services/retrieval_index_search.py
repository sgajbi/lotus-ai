from __future__ import annotations

from dataclasses import dataclass

from app.contracts.retrieval import (
    RetrievalExecutionRequest,
    RetrievalIndexedChunkDescriptor,
    RetrievalSearchHit,
)
from app.repositories.retrieval_repository import RetrievalRepository
from app.retrieval.foundation_embedding import build_preview_embedding, cosine_similarity
from app.services.retrieval_text_scoring import lexical_overlap_ratio, tokenize_retrieval_text


@dataclass(frozen=True)
class IndexedRetrievalSearchResult:
    indexed_chunks_available: bool
    hits: list[RetrievalSearchHit]


def search_indexed_chunks(
    *,
    repository: RetrievalRepository,
    request: RetrievalExecutionRequest,
) -> IndexedRetrievalSearchResult:
    indexed_chunks = repository.list_searchable_indexed_chunks(request.source_ids)
    if not indexed_chunks:
        return IndexedRetrievalSearchResult(indexed_chunks_available=False, hits=[])

    query_terms = tokenize_retrieval_text(request.query)
    query_embedding = build_preview_embedding(request.query)
    ranked_hits: list[tuple[float, RetrievalIndexedChunkDescriptor]] = []
    for chunk in indexed_chunks:
        score = _score_indexed_chunk(
            query_terms=query_terms,
            query_embedding=query_embedding,
            chunk=chunk,
        )
        if score <= 0.0:
            continue
        ranked_hits.append((score, chunk))

    ranked_hits.sort(
        key=lambda item: (
            -item[0],
            item[1].source_id,
            item[1].document_id,
            item[1].chunk_id,
        )
    )
    hits = [
        RetrievalSearchHit(
            source_id=chunk.source_id,
            document_id=chunk.document_id,
            chunk_id=chunk.chunk_id,
            score=round(score, 6),
            snippet=chunk.snippet,
        )
        for score, chunk in ranked_hits[: request.limit]
    ]
    return IndexedRetrievalSearchResult(indexed_chunks_available=True, hits=hits)


def _score_indexed_chunk(
    *,
    query_terms: set[str],
    query_embedding: list[float],
    chunk: RetrievalIndexedChunkDescriptor,
) -> float:
    lexical_score = lexical_overlap_ratio(
        query_terms=query_terms,
        searchable_text=f"{chunk.document_title} {chunk.snippet}",
    )
    if lexical_score == 0.0:
        return 0.0
    vector_score = cosine_similarity(query_embedding, chunk.embedding_vector)
    return (vector_score * 0.75) + (lexical_score * 0.25)
