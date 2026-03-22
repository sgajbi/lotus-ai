from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.contracts.retrieval import (
    RetrievalExecutionResponse,
    RetrievalExecutionStage,
    RetrievalSearchHit,
    RetrievalSearchRequest,
    RetrievalStatus,
)
from app.repositories.memory_retrieval_repository import InMemoryRetrievalRepository
from app.services.retrieval_service import search_sources


def test_search_sources_returns_catalog_only_hits_for_enabled_seeded_sources() -> None:
    request = RetrievalSearchRequest(
        query="shared ai platform service",
        caller_app="lotus-workbench",
        correlation_id="corr-ret-1",
        source_ids=["lotus-platform-rfcs"],
    )

    response = search_sources(request)

    assert response.status == RetrievalStatus.READY
    assert response.execution_stage == RetrievalExecutionStage.CATALOG_ONLY
    assert response.hits[0].source_id == "lotus-platform-rfcs"
    assert response.hits[0].score > 0.0
    assert "catalog-only hits" in response.message


def test_search_sources_returns_indexed_hits_when_live_retrieval_enabled() -> None:
    from app.config import settings

    settings.retrieval_mode = "enabled"
    request = RetrievalSearchRequest(
        query="shared ai platform service",
        caller_app="lotus-workbench",
        correlation_id="corr-ret-1-indexed",
        source_ids=["lotus-platform-rfcs"],
    )

    response = search_sources(request)

    assert response.status == RetrievalStatus.READY
    assert response.execution_stage == RetrievalExecutionStage.INDEXED_SEARCH
    assert response.hits[0].document_id == "lotus-platform-rfc-0069"
    assert "Live indexed retrieval is active" in response.message

    settings.retrieval_mode = "disabled"


def test_search_sources_rejects_disabled_source_ids_before_execution() -> None:
    request = RetrievalSearchRequest(
        query="What does RFC-0069 say?",
        caller_app="lotus-workbench",
        correlation_id="corr-ret-2",
        source_ids=["lotus-platform-standards"],
    )

    with pytest.raises(HTTPException) as exc_info:
        search_sources(request)

    assert exc_info.value.status_code == 409
    assert "not enabled" in str(exc_info.value.detail)


def test_search_sources_rejects_when_query_has_no_catalog_only_matches() -> None:
    request = RetrievalSearchRequest(
        query="zzzxqv unmatched phrase",
        caller_app="lotus-workbench",
        correlation_id="corr-ret-2b",
    )

    with pytest.raises(HTTPException) as exc_info:
        search_sources(request)

    assert exc_info.value.status_code == 409
    assert "Retrieval search is not enabled yet" in str(exc_info.value.detail)


def test_search_sources_returns_hits_for_enabled_source_subset() -> None:
    request = RetrievalSearchRequest(
        query="What does RFC-0069 say?",
        caller_app="lotus-workbench",
        correlation_id="corr-ret-3",
        source_ids=["lotus-platform-rfcs"],
    )
    repository = InMemoryRetrievalRepository()
    execution = RetrievalExecutionResponse(
        status=RetrievalStatus.READY,
        execution_stage=RetrievalExecutionStage.CATALOG_ONLY,
        vector_store="postgresql+pgvector",
        hits=[
            RetrievalSearchHit(
                source_id="lotus-platform-rfcs",
                document_id="lotus-platform-rfc-0069",
                chunk_id="chunk_rfc_0069_0001",
                score=0.98,
                snippet="RFC-0069 defines lotus-ai as the shared AI platform service.",
            )
        ],
        message="Search completed.",
    )

    with (
        patch("app.services.retrieval_service.get_retrieval_repository", return_value=repository),
        patch("app.services.retrieval_service.execute_retrieval_search", return_value=execution),
    ):
        response = search_sources(request)

    assert response.status == RetrievalStatus.READY
    assert response.execution_stage == RetrievalExecutionStage.CATALOG_ONLY
    assert response.hits[0].source_id == "lotus-platform-rfcs"
    assert response.message == "Search completed."
