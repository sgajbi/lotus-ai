from __future__ import annotations

import re
from fastapi import HTTPException, status

from app.config import settings
from app.contracts.retrieval import (
    RetrievalChunkDescriptor,
    RetrievalExecutionRequest,
    RetrievalExecutionResponse,
    RetrievalExecutionStage,
    RetrievalSearchHit,
    RetrievalStatus,
)
from app.retrieval.policy import VECTOR_STORE_STRATEGY
from app.services.retrieval_store import get_retrieval_repository


def execute_retrieval_search(request: RetrievalExecutionRequest) -> RetrievalExecutionResponse:
    if settings.retrieval_mode != "enabled":
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

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            "Retrieval execution mode is enabled in configuration but no live retrieval backend "
            "is wired yet."
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

    query_terms = _tokenize(request.query)
    if not query_terms:
        return []

    ranked_hits: list[tuple[float, str, str]] = []
    for source in enabled_sources:
        for document in repository.list_documents_for_source(source.source_id):
            for chunk in repository.list_chunks_for_document(document.document_id):
                score = _score_catalog_chunk(
                    query_terms=query_terms,
                    document_title=document.title,
                    chunk=chunk,
                )
                if score <= 0.0:
                    continue
                ranked_hits.append((score, chunk.source_id, chunk.preview))

    ranked_hits.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [
        build_catalog_only_hit(source_id=source_id, snippet=snippet, score=score)
        for score, source_id, snippet in ranked_hits[: request.limit]
    ]


def _score_catalog_chunk(
    *,
    query_terms: set[str],
    document_title: str,
    chunk: RetrievalChunkDescriptor,
) -> float:
    searchable_terms = _tokenize(f"{document_title} {chunk.preview}")
    overlap_count = len(query_terms & searchable_terms)
    if overlap_count == 0:
        return 0.0
    return overlap_count / len(query_terms)


def _tokenize(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.lower()) if token}


def build_catalog_only_hit(
    *,
    source_id: str,
    snippet: str,
    score: float,
) -> RetrievalSearchHit:
    return RetrievalSearchHit(source_id=source_id, score=score, snippet=snippet)
