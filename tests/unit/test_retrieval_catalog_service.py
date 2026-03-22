from fastapi import HTTPException

from app.services.retrieval_catalog_service import (
    get_documents_for_source,
    get_retrieval_index_status,
)


def test_get_retrieval_index_status_includes_known_sources() -> None:
    response = get_retrieval_index_status()

    assert response.service == "lotus-ai"
    assert any(source.source_id == "lotus-platform-rfcs" for source in response.sources)


def test_get_documents_for_source_returns_staged_documents() -> None:
    response = get_documents_for_source("lotus-platform-rfcs")

    assert response.source_id == "lotus-platform-rfcs"
    assert any(document.document_id == "lotus-platform-rfc-0069" for document in response.documents)


def test_get_documents_for_source_rejects_unknown_source() -> None:
    try:
        get_documents_for_source("unknown-source")
    except HTTPException as exc:
        assert exc.status_code == 404
        assert "Unknown retrieval source_id" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException for unknown source")
