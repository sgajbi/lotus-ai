from app.contracts.retrieval import RetrievalIndexJobDescriptor, RetrievalJobStatus
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
    assert any(chunk.chunk_id == "chunk_rfc_0069_0001" for chunk in chunks)


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


def test_memory_retrieval_repository_returns_existing_source_copy() -> None:
    repository = InMemoryRetrievalRepository()

    source = repository.get_source("lotus-platform-rfcs")

    assert source is not None
    assert source.source_id == "lotus-platform-rfcs"


def test_memory_retrieval_repository_initializes_document_bucket_for_new_override_source() -> None:
    repository = InMemoryRetrievalRepository()
    repository.save_index_job(
        RetrievalIndexJobDescriptor(
            job_id="retjob_new_source",
            source_id="new-source",
            status=RetrievalJobStatus.STAGED,
            document_count=0,
            chunk_count=0,
            message="New source override.",
        )
    )

    assert repository.list_documents_for_source("new-source") == []


def test_memory_retrieval_repository_updates_document_and_chunk_index_status() -> None:
    repository = InMemoryRetrievalRepository()

    repository.set_source_index_status(
        source_id="lotus-platform-rfcs",
        index_status="INDEXED",
    )

    documents = repository.list_documents_for_source("lotus-platform-rfcs")
    chunks = repository.list_chunks_for_document("lotus-platform-rfc-0069")

    assert all(document.index_status == "INDEXED" for document in documents)
    assert all(chunk.index_status == "INDEXED" for chunk in chunks)
