from app.retrieval.source_governance import build_retrieval_source_governance


def test_build_retrieval_source_governance_summarizes_enabled_and_staged_sources() -> None:
    response = build_retrieval_source_governance()

    assert response.service == "lotus-ai"
    assert response.enabled_source_count >= 2
    assert response.staged_only_source_count >= 1
    assert any(
        source.source_id == "lotus-platform-rfcs"
        and source.governance_status == "SEARCH_ENABLED"
        and source.search_enabled is True
        and source.searchable_document_count >= 1
        for source in response.sources
    )
    assert any(
        source.source_id == "lotus-platform-standards"
        and source.governance_status == "STAGED_ONLY"
        and source.search_enabled is False
        and source.staged_document_count >= 1
        for source in response.sources
    )
