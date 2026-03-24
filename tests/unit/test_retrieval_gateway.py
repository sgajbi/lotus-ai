from app.config import settings
from app.contracts.retrieval import (
    RetrievalDocumentGovernanceResponse,
    RetrievalExecutionRequest,
)
from app.repositories.memory_retrieval_repository import InMemoryRetrievalRepository
from app.services.retrieval_gateway import (
    _build_catalog_only_hits,
    _build_live_search_unavailable_message,
    execute_retrieval_search,
)


def test_build_catalog_only_hits_returns_empty_when_no_sources_are_enabled() -> None:
    repository = InMemoryRetrievalRepository()
    request = RetrievalExecutionRequest(
        query="shared ai platform service",
        caller_app="lotus-workbench",
        correlation_id="corr-ret-gateway-no-source",
        source_ids=["lotus-platform-standards"],
    )

    hits = _build_catalog_only_hits(request, repository=repository)

    assert hits == []


def test_execute_retrieval_search_returns_live_ready_with_no_matching_hits() -> None:
    settings.retrieval_mode = "enabled"
    repository = InMemoryRetrievalRepository()
    repository.set_source_index_status(
        source_id="lotus-platform-rfcs",
        index_status="INDEXED",
    )
    request = RetrievalExecutionRequest(
        query="zzzxqv unmatched phrase",
        caller_app="lotus-workbench",
        correlation_id="corr-ret-gateway-no-hit",
        source_ids=["lotus-platform-rfcs"],
    )

    try:
        from unittest.mock import patch

        with patch(
            "app.services.retrieval_gateway.get_retrieval_repository", return_value=repository
        ):
            response = execute_retrieval_search(request)
    finally:
        settings.retrieval_mode = "disabled"

    assert response.execution_stage == "LIVE_SEARCH"
    assert response.hits == []
    assert "returned no matching hits" in response.message


def test_build_live_search_unavailable_message_covers_remaining_blocker_shapes() -> None:
    assert (
        _build_live_search_unavailable_message(
            document_governance=RetrievalDocumentGovernanceResponse(
                service="lotus-ai",
                retrieval_mode="enabled",
                vector_store="postgresql+pgvector",
                searchable_document_count=1,
                index_pending_document_count=0,
                blocked_document_count=0,
                refresh_pending_document_count=0,
                withdrawn_document_count=0,
                documents=[],
            )
        )
        == "Live retrieval search is available."
    )
    assert "corpus refresh work is still in flight" in _build_live_search_unavailable_message(
        document_governance=RetrievalDocumentGovernanceResponse(
            service="lotus-ai",
            retrieval_mode="enabled",
            vector_store="postgresql+pgvector",
            searchable_document_count=0,
            index_pending_document_count=0,
            blocked_document_count=0,
            refresh_pending_document_count=1,
            withdrawn_document_count=0,
            documents=[],
        )
    )
    assert "latest governed corpus lineage is withdrawn" in _build_live_search_unavailable_message(
        document_governance=RetrievalDocumentGovernanceResponse(
            service="lotus-ai",
            retrieval_mode="enabled",
            vector_store="postgresql+pgvector",
            searchable_document_count=0,
            index_pending_document_count=0,
            blocked_document_count=0,
            refresh_pending_document_count=0,
            withdrawn_document_count=1,
            documents=[],
        )
    )
    assert "rolled back or blocked by source posture" in _build_live_search_unavailable_message(
        document_governance=RetrievalDocumentGovernanceResponse(
            service="lotus-ai",
            retrieval_mode="enabled",
            vector_store="postgresql+pgvector",
            searchable_document_count=0,
            index_pending_document_count=0,
            blocked_document_count=1,
            refresh_pending_document_count=0,
            withdrawn_document_count=0,
            documents=[],
        )
    )
    assert (
        "no promoted indexed corpus content is registered"
        in _build_live_search_unavailable_message(
            document_governance=RetrievalDocumentGovernanceResponse(
                service="lotus-ai",
                retrieval_mode="enabled",
                vector_store="postgresql+pgvector",
                searchable_document_count=0,
                index_pending_document_count=0,
                blocked_document_count=0,
                refresh_pending_document_count=0,
                withdrawn_document_count=0,
                documents=[],
            )
        )
    )
