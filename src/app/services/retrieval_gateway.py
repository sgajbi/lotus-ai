from __future__ import annotations

from app.config import settings
from app.contracts.retrieval import (
    RetrievalDocumentGovernanceResponse,
    RetrievalExecutionRequest,
    RetrievalExecutionResponse,
    RetrievalExecutionStage,
    RetrievalSearchHit,
    RetrievalStatus,
)
from app.repositories.retrieval_repository import RetrievalRepository
from app.retrieval.document_governance import build_retrieval_document_governance
from app.retrieval.policy import VECTOR_STORE_STRATEGY
from app.retrieval.search_scoring import score_terms
from app.services.retrieval_store import get_retrieval_repository


def execute_retrieval_search(request: RetrievalExecutionRequest) -> RetrievalExecutionResponse:
    repository = get_retrieval_repository()
    if settings.retrieval_mode != "enabled":
        catalog_hits = _build_catalog_only_hits(request, repository=repository)
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

    document_governance = build_retrieval_document_governance(
        source_ids=request.source_ids,
        repository=repository,
    )
    if document_governance.searchable_document_count == 0:
        return RetrievalExecutionResponse(
            status=RetrievalStatus.REJECTED,
            execution_stage=RetrievalExecutionStage.INDEXING_DISABLED,
            vector_store=VECTOR_STORE_STRATEGY,
            hits=[],
            message=_build_live_search_unavailable_message(document_governance=document_governance),
        )

    live_hits = repository.search_indexed_chunks(
        query=request.query,
        source_ids=request.source_ids,
        limit=request.limit,
    )
    return RetrievalExecutionResponse(
        status=RetrievalStatus.READY,
        execution_stage=RetrievalExecutionStage.LIVE_SEARCH,
        vector_store=VECTOR_STORE_STRATEGY,
        hits=live_hits,
        message=(
            "Live retrieval search executed over indexed promoted corpus content."
            if live_hits
            else (
                "Live retrieval search executed over indexed promoted corpus content but returned "
                "no matching hits."
            )
        ),
    )


def _build_live_search_unavailable_message(
    *, document_governance: RetrievalDocumentGovernanceResponse
) -> str:
    searchable_document_count = document_governance.searchable_document_count
    refresh_pending_document_count = document_governance.refresh_pending_document_count
    withdrawn_document_count = document_governance.withdrawn_document_count
    index_pending_document_count = document_governance.index_pending_document_count
    blocked_document_count = document_governance.blocked_document_count
    if searchable_document_count > 0:
        return "Live retrieval search is available."
    if refresh_pending_document_count > 0:
        return (
            "Live retrieval search is enabled but currently blocked because governed corpus refresh "
            "work is still in flight."
        )
    if withdrawn_document_count > 0:
        return (
            "Live retrieval search is enabled but currently blocked because the latest governed "
            "corpus lineage is withdrawn."
        )
    if index_pending_document_count > 0:
        return (
            "Live retrieval search is enabled but currently blocked because promoted corpus "
            "indexing is still pending."
        )
    if blocked_document_count > 0:
        return (
            "Live retrieval search is enabled but currently blocked because the promoted corpus "
            "is rolled back or blocked by source posture."
        )
    return (
        "Live retrieval search is enabled but currently blocked because no promoted indexed corpus "
        "content is registered."
    )


def _build_catalog_only_hits(
    request: RetrievalExecutionRequest, *, repository: RetrievalRepository
) -> list[RetrievalSearchHit]:
    requested_source_ids = set(request.source_ids)
    enabled_sources = [
        source
        for source in repository.list_sources()
        if source.enabled and (not requested_source_ids or source.source_id in requested_source_ids)
    ]
    if not enabled_sources:
        return []

    ranked_hits: list[RetrievalSearchHit] = []
    for source in enabled_sources:
        for document in repository.list_documents_for_source(source.source_id):
            for chunk in repository.list_chunks_for_document(document.document_id):
                score = score_terms(
                    query=request.query,
                    searchable_text=f"{document.title} {chunk.preview}",
                )
                if score <= 0.0:
                    continue
                ranked_hits.append(
                    build_catalog_only_hit(
                        source_id=chunk.source_id,
                        document_id=chunk.document_id,
                        chunk_id=chunk.chunk_id,
                        snippet=chunk.preview,
                        score=score,
                    )
                )

    ranked_hits.sort(key=lambda hit: (-hit.score, hit.source_id, hit.document_id, hit.chunk_id))
    return ranked_hits[: request.limit]


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
