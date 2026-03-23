import pytest

from app.config import settings
from app.contracts.retrieval import RetrievalExecutionRequest
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


def test_execute_retrieval_search_returns_live_hits_when_enabled() -> None:
    settings.retrieval_mode = "enabled"
    repository = InMemoryRetrievalRepository()
    repository.set_source_index_status(
        source_id="lotus-platform-rfcs",
        index_status="INDEXED",
    )

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "app.services.retrieval_gateway.get_retrieval_repository",
            lambda: repository,
        )
        monkeypatch.setattr(
            "app.retrieval.document_governance.get_retrieval_repository",
            lambda: repository,
        )
        response = execute_retrieval_search(
            RetrievalExecutionRequest(
                query="shared ai platform service",
                caller_app="lotus-workbench",
                correlation_id="corr-ret-gw-2",
                source_ids=["lotus-platform-rfcs"],
                limit=5,
            )
        )

    assert response.status == "READY"
    assert response.execution_stage == "LIVE_SEARCH"
    assert response.hits
    assert response.hits[0].source_id == "lotus-platform-rfcs"
    assert response.hits[0].document_id == "lotus-platform-rfc-0069"
    assert response.hits[0].chunk_id == "chunk_rfc_0069_0001"
    assert "Live retrieval search executed" in response.message

    settings.retrieval_mode = "disabled"


def test_execute_retrieval_search_rejects_live_requests_when_searchable_corpus_is_unavailable() -> None:
    settings.retrieval_mode = "enabled"
    repository = InMemoryRetrievalRepository()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "app.services.retrieval_gateway.get_retrieval_repository",
            lambda: repository,
        )
        monkeypatch.setattr(
            "app.retrieval.document_governance.get_retrieval_repository",
            lambda: repository,
        )
        response = execute_retrieval_search(
            RetrievalExecutionRequest(
                query="shared ai platform service",
                caller_app="lotus-workbench",
                correlation_id="corr-ret-gw-3",
                source_ids=["lotus-platform-rfcs"],
                limit=5,
            )
        )

    assert response.status == "REJECTED"
    assert response.execution_stage == "INDEXING_DISABLED"
    assert response.hits == []
    assert "indexing is still pending" in response.message

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
