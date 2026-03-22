from __future__ import annotations

from app.config import settings
from app.contracts.retrieval import (
    RetrievalChunkDescriptor,
    RetrievalDocumentPromotionStatus,
    RetrievalExecutionRequest,
    RetrievalExecutionResponse,
    RetrievalExecutionStage,
    RetrievalSearchHit,
    RetrievalStatus,
)
from app.retrieval.policy import VECTOR_STORE_STRATEGY
from app.services.retrieval_index_search import search_indexed_chunks
from app.services.retrieval_store import get_retrieval_repository
from app.services.retrieval_text_scoring import lexical_overlap_ratio, tokenize_retrieval_text


def execute_retrieval_search(request: RetrievalExecutionRequest) -> RetrievalExecutionResponse:
    repository = get_retrieval_repository()
    if settings.retrieval_mode == "enabled":
        indexed_result = search_indexed_chunks(repository=repository, request=request)
        if indexed_result.indexed_chunks_available:
            return RetrievalExecutionResponse(
                status=RetrievalStatus.READY,
                execution_stage=RetrievalExecutionStage.INDEXED_SEARCH,
                vector_store=VECTOR_STORE_STRATEGY,
                hits=indexed_result.hits,
                message=(
                    "Live indexed retrieval is active. Returning bounded hits from promoted "
                    "persisted chunk embeddings."
                ),
            )
        return RetrievalExecutionResponse(
            status=RetrievalStatus.REJECTED,
            execution_stage=RetrievalExecutionStage.INDEXING_DISABLED,
            vector_store=VECTOR_STORE_STRATEGY,
            hits=[],
            message=(
                "Retrieval execution is enabled in configuration, but no promoted indexed chunks "
                "are available for the requested scope."
            ),
        )

    catalog_hits = _build_catalog_only_hits(request)
    if catalog_hits:
        return RetrievalExecutionResponse(
            status=RetrievalStatus.READY,
            execution_stage=RetrievalExecutionStage.CATALOG_ONLY,
            vector_store=VECTOR_STORE_STRATEGY,
            hits=catalog_hits,
            message=(
                "Live retrieval search is not enabled yet. Returning deterministic "
                "catalog-only hits from staged approved sources."
            ),
        )
    return RetrievalExecutionResponse(
        status=RetrievalStatus.REJECTED,
        execution_stage=RetrievalExecutionStage.SEARCH_DISABLED,
        vector_store=VECTOR_STORE_STRATEGY,
        hits=[],
        message=(
            "Retrieval search is not enabled yet. lotus-ai currently exposes governed "
            "catalog and indexing contracts before live search is active."
        ),
    )


def _build_catalog_only_hits(request: RetrievalExecutionRequest) -> list[RetrievalSearchHit]:
    repository = get_retrieval_repository()
    requested_source_ids = set(request.source_ids)
    enabled_sources = [
        source
        for source in repository.list_sources()
        if source.enabled and (not requested_source_ids or source.source_id in requested_source_ids)
    ]
    if not enabled_sources:
        return []

    query_terms = tokenize_retrieval_text(request.query)
    if not query_terms:
        return []

    ranked_hits: list[tuple[float, str, str, str, str]] = []
    for source in enabled_sources:
        for document in repository.list_documents_for_source(source.source_id):
            if document.promotion_status != RetrievalDocumentPromotionStatus.SEARCHABLE:
                continue
            for chunk in repository.list_chunks_for_document(document.document_id):
                score = _score_catalog_chunk(
                    query_terms=query_terms,
                    document_title=document.title,
                    chunk=chunk,
                )
                if score <= 0.0:
                    continue
                ranked_hits.append(
                    (score, chunk.source_id, chunk.document_id, chunk.chunk_id, chunk.preview)
                )

    ranked_hits.sort(key=lambda item: (-item[0], item[1], item[2], item[3], item[4]))
    return [
        build_catalog_only_hit(
            source_id=source_id,
            document_id=document_id,
            chunk_id=chunk_id,
            snippet=snippet,
            score=score,
        )
        for score, source_id, document_id, chunk_id, snippet in ranked_hits[: request.limit]
    ]


def _score_catalog_chunk(
    *,
    query_terms: set[str],
    document_title: str,
    chunk: RetrievalChunkDescriptor,
) -> float:
    return lexical_overlap_ratio(
        query_terms=query_terms,
        searchable_text=f"{document_title} {chunk.preview}",
    )


def build_catalog_only_hit(
    *,
    source_id: str,
    document_id: str,
    chunk_id: str,
    snippet: str,
    score: float,
) -> RetrievalSearchHit:
    return RetrievalSearchHit(
        source_id=source_id,
        document_id=document_id,
        chunk_id=chunk_id,
        score=score,
        snippet=snippet,
    )
