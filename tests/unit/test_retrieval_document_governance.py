from app.repositories.memory_retrieval_repository import InMemoryRetrievalRepository
from app.retrieval.document_governance import build_retrieval_document_governance


def test_build_retrieval_document_governance_reflects_default_document_posture() -> None:
    response = build_retrieval_document_governance()

    assert response.service == "lotus-ai"
    assert response.searchable_document_count == 0
    assert response.index_pending_document_count >= 3
    assert response.blocked_document_count >= 1
    assert any(
        document.document_id == "lotus-platform-rfc-0069"
        and document.governance_status == "INDEX_PENDING"
        and document.search_enabled is False
        for document in response.documents
    )
    assert any(
        document.document_id == "lotus-platform-observability-standards"
        and document.governance_status == "BLOCKED_BY_SOURCE"
        and document.search_enabled is False
        for document in response.documents
    )


def test_build_retrieval_document_governance_marks_indexed_enabled_documents_searchable() -> None:
    from unittest.mock import patch

    repository = InMemoryRetrievalRepository()
    repository.set_source_index_status(
        source_id="lotus-platform-rfcs",
        index_status="INDEXED",
    )

    with patch(
        "app.retrieval.document_governance.get_retrieval_repository", return_value=repository
    ):
        response = build_retrieval_document_governance()

    assert response.searchable_document_count >= 2
    assert any(
        document.document_id == "lotus-platform-rfc-0069"
        and document.governance_status == "SEARCH_ENABLED"
        and document.search_enabled is True
        for document in response.documents
    )
