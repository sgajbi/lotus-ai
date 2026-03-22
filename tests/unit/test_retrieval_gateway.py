from unittest.mock import patch

from app.config import settings
from app.contracts.retrieval import (
    RetrievalDocumentPromotionStatus,
    RetrievalExecutionRequest,
)
from app.repositories.memory_retrieval_repository import InMemoryRetrievalRepository
from app.services.retrieval_gateway import build_catalog_only_hit, execute_retrieval_search


def test_execute_retrieval_search_returns_catalog_only_hits_when_disabled() -> None:
    response = execute_retrieval_search(
        RetrievalExecutionRequest(
            query="shared ai platform service",
            caller_app="lotus-workbench",
            correlation_id="corr-ret-gw-1",
            source_ids=[],
            limit=5,
        )
    )

    assert response.status == "READY"
    assert response.execution_stage == "CATALOG_ONLY"
    assert response.vector_store == "postgresql+pgvector"
    assert response.hits
    assert response.hits[0].source_id in {"lotus-platform-rfcs", "lotus-ai-architecture"}
    assert response.hits[0].document_id
    assert response.hits[0].chunk_id


def test_execute_retrieval_search_returns_indexed_hits_when_enabled() -> None:
    settings.retrieval_mode = "enabled"

    response = execute_retrieval_search(
        RetrievalExecutionRequest(
            query="What does RFC-0069 say?",
            caller_app="lotus-workbench",
            correlation_id="corr-ret-gw-2",
            source_ids=[],
            limit=5,
        )
    )

    assert response.status == "READY"
    assert response.execution_stage == "INDEXED_SEARCH"
    assert response.hits
    assert response.hits[0].document_id == "lotus-platform-rfc-0069"

    settings.retrieval_mode = "disabled"


def test_build_catalog_only_hit_returns_zero_scored_catalog_hit() -> None:
    hit = build_catalog_only_hit(
        source_id="lotus-platform-rfcs",
        document_id="lotus-platform-rfc-0069",
        chunk_id="chunk_rfc_0069_0001",
        snippet="RFC-0069 introduces lotus-ai.",
        score=0.0,
    )

    assert hit.source_id == "lotus-platform-rfcs"
    assert hit.document_id == "lotus-platform-rfc-0069"
    assert hit.chunk_id == "chunk_rfc_0069_0001"
    assert hit.score == 0.0
    assert "lotus-ai" in hit.snippet


def test_execute_retrieval_search_ignores_staged_only_documents() -> None:
    repository = InMemoryRetrievalRepository()
    searchable_document = repository._documents["lotus-platform-rfcs"][0]  # noqa: SLF001
    repository._documents["lotus-platform-rfcs"] = [  # noqa: SLF001
        searchable_document.model_copy(
            update={"promotion_status": RetrievalDocumentPromotionStatus.STAGED}
        )
    ]
    repository._chunks = {  # noqa: SLF001
        searchable_document.document_id: repository.list_chunks_for_document(
            searchable_document.document_id
        )
    }

    with patch("app.services.retrieval_gateway.get_retrieval_repository", return_value=repository):
        response = execute_retrieval_search(
            RetrievalExecutionRequest(
                query="shared infrastructure ownership",
                caller_app="lotus-workbench",
                correlation_id="corr-ret-gw-3",
                source_ids=["lotus-platform-rfcs"],
                limit=5,
            )
        )

    assert response.status == "REJECTED"
    assert response.execution_stage == "SEARCH_DISABLED"
    assert response.hits == []


def test_execute_retrieval_search_rejects_enabled_mode_without_indexed_chunks() -> None:
    settings.retrieval_mode = "enabled"
    repository = InMemoryRetrievalRepository()
    repository._documents["lotus-platform-rfcs"] = [  # noqa: SLF001
        document.model_copy(update={"promotion_status": RetrievalDocumentPromotionStatus.STAGED})
        for document in repository._documents["lotus-platform-rfcs"]  # noqa: SLF001
    ]

    with patch("app.services.retrieval_gateway.get_retrieval_repository", return_value=repository):
        response = execute_retrieval_search(
            RetrievalExecutionRequest(
                query="shared ai platform service",
                caller_app="lotus-workbench",
                correlation_id="corr-ret-gw-4",
                source_ids=["lotus-platform-rfcs"],
                limit=5,
            )
        )

    assert response.status == "REJECTED"
    assert response.execution_stage == "INDEXING_DISABLED"
    assert "no promoted indexed chunks" in response.message

    settings.retrieval_mode = "disabled"
