import pytest
from fastapi import HTTPException

from app.config import settings
from app.contracts.retrieval import RetrievalExecutionRequest
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


def test_execute_retrieval_search_rejects_enabled_mode_without_live_backend() -> None:
    settings.retrieval_mode = "enabled"

    with pytest.raises(HTTPException) as exc_info:
        execute_retrieval_search(
            RetrievalExecutionRequest(
                query="What does RFC-0069 say?",
                caller_app="lotus-workbench",
                correlation_id="corr-ret-gw-2",
                source_ids=[],
                limit=5,
            )
        )

    assert exc_info.value.status_code == 503
    assert "no live retrieval backend is wired yet" in str(exc_info.value.detail)

    settings.retrieval_mode = "disabled"


def test_build_catalog_only_hit_returns_zero_scored_catalog_hit() -> None:
    hit = build_catalog_only_hit(
        source_id="lotus-platform-rfcs",
        snippet="RFC-0069 introduces lotus-ai.",
        score=0.0,
    )

    assert hit.source_id == "lotus-platform-rfcs"
    assert hit.score == 0.0
    assert "lotus-ai" in hit.snippet
