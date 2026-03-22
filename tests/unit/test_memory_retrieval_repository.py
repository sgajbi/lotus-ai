from app.repositories.memory_retrieval_repository import InMemoryRetrievalRepository


def test_memory_retrieval_repository_returns_seeded_sources() -> None:
    repository = InMemoryRetrievalRepository()

    sources = repository.list_sources()

    assert any(source.source_id == "lotus-platform-rfcs" for source in sources)


def test_memory_retrieval_repository_returns_seeded_document_and_chunks() -> None:
    repository = InMemoryRetrievalRepository()

    document = repository.get_document("lotus-platform-rfc-0069")
    chunks = repository.list_chunks_for_document("lotus-platform-rfc-0069")

    assert document is not None
    assert document.source_id == "lotus-platform-rfcs"
    assert any(
        chunk.chunk_id == "chunk_rfc_0069_0001"
        and chunk.content_checksum == "sha256:chunk-rfc-0069-0001"
        for chunk in chunks
    )
    assert repository.count_embedding_records() >= 4
    assert repository.count_embedding_records_for_source("lotus-platform-rfcs") >= 2


def test_memory_retrieval_repository_returns_none_or_empty_for_unknown_records() -> None:
    repository = InMemoryRetrievalRepository()

    assert repository.get_source("missing-source") is None
    assert repository.get_document("missing-document") is None
    assert repository.get_index_job("missing-job") is None
    assert repository.list_documents_for_source("missing-source") == []
    assert repository.list_chunks_for_document("missing-document") == []


def test_memory_retrieval_repository_marks_empty_sources_as_pending_index_jobs() -> None:
    repository = InMemoryRetrievalRepository()

    job = repository.get_index_job("retjob_lotus_openapi_derived")

    assert job is not None
    assert job.source_id == "lotus-openapi-derived"
    assert job.status == "PENDING"
    assert job.document_count == 0
    assert job.embedding_record_count == 0
