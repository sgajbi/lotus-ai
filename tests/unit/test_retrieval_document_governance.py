from app.retrieval.document_governance import build_retrieval_document_governance


def test_build_retrieval_document_governance_summarizes_searchable_and_staged_documents() -> None:
    response = build_retrieval_document_governance()

    assert response.service == "lotus-ai"
    assert response.document_count >= 5
    assert response.searchable_document_count >= 4
    assert response.staged_document_count >= 1
    assert any(
        document.document_id == "lotus-platform-rfc-0069"
        and document.promotion_status == "SEARCHABLE"
        and document.search_enabled is True
        for document in response.documents
    )
    assert any(
        document.document_id == "lotus-platform-observability-standards"
        and document.promotion_status == "STAGED"
        and document.search_enabled is False
        for document in response.documents
    )
