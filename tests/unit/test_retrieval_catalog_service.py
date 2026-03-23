from unittest.mock import patch

from fastapi import HTTPException

from app.contracts.retrieval import (
    RetrievalDocumentDescriptor,
    RetrievalIndexStatus,
    RetrievalSourceDescriptor,
    RetrievalSourceKind,
)
from app.repositories.memory_retrieval_repository import InMemoryRetrievalRepository
from app.services.retrieval_catalog_service import (
    get_documents_for_source,
    get_retrieval_document_governance,
    get_retrieval_index_status,
    get_retrieval_source_governance,
    get_chunks_for_document,
)


def test_get_retrieval_index_status_includes_known_sources() -> None:
    response = get_retrieval_index_status()

    assert response.service == "lotus-ai"
    assert any(source.source_id == "lotus-platform-rfcs" for source in response.sources)


def test_get_retrieval_source_governance_reflects_live_search_posture() -> None:
    response = get_retrieval_source_governance()

    assert response.searchable_source_count == 0
    assert response.index_pending_source_count >= 2


def test_get_retrieval_document_governance_reflects_document_search_posture() -> None:
    response = get_retrieval_document_governance()

    assert response.searchable_document_count == 0
    assert any(document.document_id == "lotus-platform-rfc-0069" for document in response.documents)


def test_get_retrieval_index_status_marks_sources_as_indexed_and_not_indexed() -> None:
    repository = InMemoryRetrievalRepository()
    repository._sources = [  # noqa: SLF001 - targeted seeded-state override
        RetrievalSourceDescriptor(
            source_id="indexed-source",
            kind=RetrievalSourceKind.ARCHITECTURE,
            enabled=True,
            description="Indexed source.",
        ),
        RetrievalSourceDescriptor(
            source_id="empty-source",
            kind=RetrievalSourceKind.OPENAPI,
            enabled=False,
            description="No documents yet.",
        ),
    ]
    repository._documents = {  # noqa: SLF001 - targeted seeded-state override
        "indexed-source": [
            RetrievalDocumentDescriptor(
                document_id="indexed-doc",
                source_id="indexed-source",
                title="Indexed Doc",
                location="docs/indexed.md",
                chunk_count=1,
                index_status=RetrievalIndexStatus.INDEXED,
            )
        ],
        "empty-source": [],
    }
    repository._chunks = {  # noqa: SLF001 - targeted seeded-state override
        "indexed-doc": repository.list_chunks_for_document("lotus-platform-rfc-0069")
    }

    with (
        patch("app.retrieval.document_registry.get_retrieval_repository", return_value=repository),
        patch("app.retrieval.inventory_summary.get_retrieval_repository", return_value=repository),
    ):
        response = get_retrieval_index_status()

    indexed_status = next(
        source for source in response.sources if source.source_id == "indexed-source"
    )
    empty_status = next(source for source in response.sources if source.source_id == "empty-source")
    assert indexed_status.index_status == RetrievalIndexStatus.INDEXED
    assert empty_status.index_status == RetrievalIndexStatus.NOT_INDEXED


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


def test_get_chunks_for_document_rejects_unknown_document() -> None:
    try:
        get_chunks_for_document("unknown-document")
    except HTTPException as exc:
        assert exc.status_code == 404
        assert "Unknown retrieval document_id" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException for unknown document")
