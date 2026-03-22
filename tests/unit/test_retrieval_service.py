from fastapi import HTTPException

from app.contracts.retrieval import RetrievalSearchRequest
from app.services.retrieval_service import search_sources


def test_search_sources_rejects_when_retrieval_is_disabled() -> None:
    request = RetrievalSearchRequest(
        query="What does RFC-0069 say?",
        caller_app="lotus-workbench",
        correlation_id="corr-ret-1",
    )

    try:
        search_sources(request)
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "Retrieval search is not enabled yet" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException when retrieval is disabled")
