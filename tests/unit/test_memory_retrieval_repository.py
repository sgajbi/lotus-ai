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


def test_memory_retrieval_repository_returns_searchable_indexed_chunks() -> None:
    repository = InMemoryRetrievalRepository()

    indexed_chunks = repository.list_searchable_indexed_chunks(["lotus-platform-rfcs"])

    assert indexed_chunks
    assert indexed_chunks[0].source_id == "lotus-platform-rfcs"
    assert indexed_chunks[0].embedding_status == "PERSISTED"
    assert indexed_chunks[0].vector_dimensions == 16
    assert len(indexed_chunks[0].embedding_vector) == 16


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


def test_memory_retrieval_repository_marks_searchable_indexed_sources_as_completed_jobs() -> None:
    repository = InMemoryRetrievalRepository()

    job = repository.get_index_job("retjob_lotus_platform_rfcs")

    assert job is not None
    assert job.status == "COMPLETED"
    assert "persisted embeddings" in job.message


def test_memory_retrieval_repository_exposes_persisted_job_events() -> None:
    repository = InMemoryRetrievalRepository()

    events = repository.list_index_job_events("retjob_lotus_platform_standards")

    assert any(event.status == "FAILED" for event in events)
    assert any("promoted into searchable scope" in event.notes for event in events)


def test_memory_retrieval_repository_refreshes_searchable_job() -> None:
    repository = InMemoryRetrievalRepository()

    refresh = repository.refresh_index_job("retjob_lotus_platform_rfcs")

    assert refresh is not None
    assert refresh.status == "COMPLETED"
    assert refresh.refreshed_document_count == 2
    assert refresh.refreshed_chunk_count >= 2
    assert refresh.replayed_embedding_count >= 2
    assert refresh.event.stage == "ENABLED"
    job = repository.get_index_job("retjob_lotus_platform_rfcs")
    assert job is not None
    assert job.status == "COMPLETED"


def test_memory_retrieval_repository_blocks_refresh_without_searchable_documents() -> None:
    repository = InMemoryRetrievalRepository()

    refresh = repository.refresh_index_job("retjob_lotus_platform_standards")

    assert refresh is not None
    assert refresh.status == "BLOCKED"
    assert refresh.refreshed_document_count == 0
    assert refresh.event.status == "FAILED"
    assert "no searchable documents" in refresh.message
