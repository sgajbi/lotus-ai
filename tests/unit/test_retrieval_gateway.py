from app.contracts.retrieval import RetrievalExecutionRequest
from app.services.retrieval_gateway import execute_retrieval_search


def test_execute_retrieval_search_returns_rejected_stage_when_disabled() -> None:
    response = execute_retrieval_search(
        RetrievalExecutionRequest(
            query="What does RFC-0069 say?",
            caller_app="lotus-workbench",
            correlation_id="corr-ret-gw-1",
            source_ids=[],
            limit=5,
        )
    )

    assert response.status == "REJECTED"
    assert response.execution_stage == "SEARCH_DISABLED"
    assert response.vector_store == "postgresql+pgvector"
    assert response.hits == []
