from app.contracts.retrieval import RetrievalExecutionRequest
from app.repositories.memory_retrieval_repository import InMemoryRetrievalRepository
from app.services.retrieval_index_search import search_indexed_chunks


def test_search_indexed_chunks_returns_ranked_hits_for_matching_query() -> None:
    repository = InMemoryRetrievalRepository()

    result = search_indexed_chunks(
        repository=repository,
        request=RetrievalExecutionRequest(
            query="shared ai platform service",
            caller_app="lotus-workbench",
            correlation_id="corr-indexed-1",
            source_ids=["lotus-platform-rfcs"],
            limit=3,
        ),
    )

    assert result.indexed_chunks_available is True
    assert result.hits
    assert result.hits[0].document_id == "lotus-platform-rfc-0069"
    assert result.hits[0].chunk_id == "chunk_rfc_0069_0001"
    assert result.hits[0].score > 0.0


def test_search_indexed_chunks_returns_empty_hits_for_non_matching_query() -> None:
    repository = InMemoryRetrievalRepository()

    result = search_indexed_chunks(
        repository=repository,
        request=RetrievalExecutionRequest(
            query="zzzxqv unmatched phrase",
            caller_app="lotus-workbench",
            correlation_id="corr-indexed-2",
            source_ids=["lotus-platform-rfcs"],
            limit=3,
        ),
    )

    assert result.indexed_chunks_available is True
    assert result.hits == []
