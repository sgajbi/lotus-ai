from app.retrieval.source_governance import build_retrieval_source_governance


def test_build_retrieval_source_governance_reflects_live_search_eligibility() -> None:
    response = build_retrieval_source_governance()

    assert response.service == "lotus-ai"
    assert response.searchable_source_count == 0
    assert response.index_pending_source_count >= 2
    assert response.blocked_source_count >= 1
    assert any(
        source.source_id == "lotus-platform-rfcs"
        and source.governance_status == "INDEX_PENDING"
        and source.search_enabled is False
        for source in response.sources
    )
    assert any(
        source.source_id == "lotus-platform-standards"
        and source.governance_status == "BLOCKED_BY_SOURCE"
        and source.search_enabled is False
        for source in response.sources
    )
