from app.contracts.retrieval import (
    RetrievalEmbeddingStatus,
    RetrievalExecutionRequest,
    RetrievalIndexStatus,
)
from app.repositories.memory_retrieval_repository import InMemoryRetrievalRepository


def test_memory_retrieval_repository_returns_seeded_sources() -> None:
    repository = InMemoryRetrievalRepository()

    sources = repository.list_sources()

    assert any(source.source_id == "lotus-platform-rfcs" for source in sources)
    source = repository.get_source("lotus-platform-rfcs")
    assert source is not None
    assert source.source_id == "lotus-platform-rfcs"


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


def test_memory_retrieval_repository_searches_indexed_hits() -> None:
    repository = InMemoryRetrievalRepository()

    hits = repository.search_indexed_hits(
        RetrievalExecutionRequest(
            query="shared ai platform service",
            caller_app="lotus-workbench",
            correlation_id="corr-mem-search-1",
            source_ids=["lotus-platform-rfcs"],
            limit=3,
        )
    )

    assert hits
    assert hits[0].document_id == "lotus-platform-rfc-0069"
    assert hits[0].score > 0.0


def test_memory_retrieval_repository_returns_none_or_empty_for_unknown_records() -> None:
    repository = InMemoryRetrievalRepository()

    assert repository.get_source("missing-source") is None
    assert repository.get_document("missing-document") is None
    assert repository.get_index_job("missing-job") is None
    assert repository.list_documents_for_source("missing-source") == []
    assert repository.list_chunks_for_document("missing-document") == []


def test_memory_retrieval_repository_skips_invalid_indexed_chunk_records() -> None:
    repository = InMemoryRetrievalRepository()
    original_record = dict(repository._embedding_records["emb_chunk_rfc_0069_0001"])
    original_document = repository._documents["lotus-platform-rfcs"][1]
    original_chunk = repository._chunks["lotus-platform-rfc-0069"][0]

    repository._embedding_records["emb_chunk_rfc_0069_0001"]["document_id"] = "missing-document"
    repository.list_searchable_indexed_chunks(["lotus-platform-rfcs"])

    repository._embedding_records["emb_chunk_rfc_0069_0001"] = dict(original_record)
    original_document.index_status = RetrievalIndexStatus.STAGED
    repository.list_searchable_indexed_chunks(["lotus-platform-rfcs"])

    original_document.index_status = RetrievalIndexStatus.INDEXED
    original_chunk.index_status = RetrievalIndexStatus.STAGED
    repository.list_searchable_indexed_chunks(["lotus-platform-rfcs"])

    original_chunk.index_status = RetrievalIndexStatus.INDEXED
    repository._embedding_records["emb_chunk_rfc_0069_0001"]["embedding_status"] = (
        RetrievalEmbeddingStatus.STAGED
    )
    repository.list_searchable_indexed_chunks(["lotus-platform-rfcs"])

    repository._embedding_records["emb_chunk_rfc_0069_0001"]["embedding_status"] = (
        RetrievalEmbeddingStatus.PERSISTED
    )
    repository._embedding_records["emb_chunk_rfc_0069_0001"]["content_checksum"] = "sha256:mismatch"
    repository.list_searchable_indexed_chunks(["lotus-platform-rfcs"])

    repository._embedding_records["emb_chunk_rfc_0069_0001"] = original_record
    original_document.index_status = RetrievalIndexStatus.INDEXED
    original_chunk.index_status = RetrievalIndexStatus.INDEXED


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


def test_memory_retrieval_repository_refresh_returns_none_for_unknown_job() -> None:
    repository = InMemoryRetrievalRepository()

    assert repository.refresh_index_job("missing-job") is None


def test_memory_retrieval_repository_refresh_recreates_missing_embedding_record() -> None:
    repository = InMemoryRetrievalRepository()
    del repository._embedding_records["emb_chunk_rfc_0068_0001"]

    refresh = repository.refresh_index_job("retjob_lotus_platform_rfcs")

    assert refresh is not None
    assert refresh.persisted_embedding_count >= 1
    assert "emb_chunk_rfc_0068_0001" in repository._embedding_records


def test_memory_retrieval_repository_refresh_replaces_legacy_embedding_id() -> None:
    repository = InMemoryRetrievalRepository()
    repository._embedding_records["legacy_embedding_rfc_0068"] = repository._embedding_records.pop(
        "emb_chunk_rfc_0068_0001"
    )

    refresh = repository.refresh_index_job("retjob_lotus_platform_rfcs")

    assert refresh is not None
    assert "legacy_embedding_rfc_0068" not in repository._embedding_records
    assert "emb_chunk_rfc_0068_0001" in repository._embedding_records
    assert repository._find_embedding_id_for_chunk("missing-chunk") is None
