from pathlib import Path

from app.contracts.retrieval import RetrievalExecutionRequest
from app.db.models import RetrievalChunkEmbeddingModel
from app.repositories.sqlalchemy_retrieval_repository import SqlAlchemyRetrievalRepository
from tests.support.migration_runner import upgrade_database_to_head


def test_sqlalchemy_retrieval_repository_returns_seeded_catalog(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-retrieval.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyRetrievalRepository(database_url)

    sources = repository.list_sources()
    documents = repository.list_documents_for_source("lotus-platform-rfcs")
    chunks = repository.list_chunks_for_document("lotus-platform-rfc-0069")
    job = repository.get_index_job("retjob_lotus_platform_rfcs")

    assert any(source.source_id == "lotus-platform-rfcs" for source in sources)
    source = repository.get_source("lotus-platform-rfcs")
    assert source is not None
    assert source.source_id == "lotus-platform-rfcs"
    document = repository.get_document("lotus-platform-rfc-0069")
    assert document is not None
    assert document.document_id == "lotus-platform-rfc-0069"
    assert any(
        document.document_id == "lotus-platform-rfc-0069"
        and document.promotion_status == "SEARCHABLE"
        for document in documents
    )
    assert any(
        chunk.chunk_id == "chunk_rfc_0069_0001"
        and chunk.content_checksum == "sha256:chunk-rfc-0069-0001"
        for chunk in chunks
    )
    assert job is not None
    assert job.source_id == "lotus-platform-rfcs"
    assert job.status == "COMPLETED"
    assert job.embedding_record_count >= 2
    assert repository.count_embedding_records() >= 4

    indexed_chunks = repository.list_searchable_indexed_chunks(["lotus-platform-rfcs"])
    assert indexed_chunks
    assert indexed_chunks[0].source_id == "lotus-platform-rfcs"
    assert indexed_chunks[0].embedding_status == "PERSISTED"
    assert indexed_chunks[0].vector_dimensions == 16
    assert len(indexed_chunks[0].embedding_vector) == 16
    assert repository.has_searchable_indexed_chunks(["lotus-platform-rfcs"]) is True
    assert repository.has_searchable_indexed_chunks(["missing-source"]) is False
    assert repository.count_embedding_records_for_source("lotus-platform-rfcs") >= 2


def test_sqlalchemy_retrieval_repository_returns_none_for_unknown_records(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-retrieval.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyRetrievalRepository(database_url)

    assert repository.get_source("missing-source") is None
    assert repository.get_document("missing-document") is None
    assert repository.get_index_job("missing-job") is None
    assert repository.list_documents_for_source("missing-source") == []
    assert repository.list_chunks_for_document("missing-document") == []
    assert repository.list_index_job_events("missing-job") == []


def test_sqlalchemy_retrieval_repository_returns_seeded_job_events(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-retrieval.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyRetrievalRepository(database_url)

    events = repository.list_index_job_events("retjob_lotus_platform_standards")

    assert any(event.status == "FAILED" for event in events)
    assert any(event.stage == "STAGED" for event in events)


def test_sqlalchemy_retrieval_repository_searches_indexed_hits(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-retrieval.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyRetrievalRepository(database_url)

    hits = repository.search_indexed_hits(
        RetrievalExecutionRequest(
            query="shared ai platform service",
            caller_app="lotus-workbench",
            correlation_id="corr-sql-search-1",
            source_ids=["lotus-platform-rfcs"],
            limit=3,
        )
    )

    assert hits
    assert hits[0].document_id == "lotus-platform-rfc-0069"
    assert hits[0].score > 0.0


def test_sqlalchemy_retrieval_repository_searches_indexed_hits_through_fallback_path(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-retrieval.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyRetrievalRepository(database_url)
    repository._database_url = "postgresql://stubbed"

    hits = repository.search_indexed_hits(
        RetrievalExecutionRequest(
            query="shared ai platform service",
            caller_app="lotus-workbench",
            correlation_id="corr-sql-search-2",
            source_ids=["lotus-platform-rfcs"],
            limit=3,
        )
    )

    assert hits
    assert hits[0].document_id == "lotus-platform-rfc-0069"


def test_sqlalchemy_retrieval_repository_refreshes_searchable_job(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-retrieval.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyRetrievalRepository(database_url)

    refresh = repository.refresh_index_job("retjob_lotus_platform_rfcs")
    events = repository.list_index_job_events("retjob_lotus_platform_rfcs")

    assert refresh is not None
    assert refresh.status == "COMPLETED"
    assert refresh.refreshed_document_count == 2
    assert refresh.replayed_embedding_count >= 2
    assert events[-1].event_id == refresh.event.event_id
    assert events[-1].stage == "ENABLED"


def test_sqlalchemy_retrieval_repository_blocks_refresh_without_searchable_documents(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-retrieval.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyRetrievalRepository(database_url)

    refresh = repository.refresh_index_job("retjob_lotus_platform_standards")

    assert refresh is not None
    assert refresh.status == "BLOCKED"
    assert refresh.event.status == "FAILED"
    assert refresh.refreshed_chunk_count == 0


def test_sqlalchemy_retrieval_repository_refresh_returns_none_for_unknown_job(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-retrieval.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyRetrievalRepository(database_url)

    assert repository.refresh_index_job("missing-job") is None


def test_sqlalchemy_retrieval_repository_refresh_recreates_missing_embedding(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-retrieval.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyRetrievalRepository(database_url)

    with repository._session_factory() as session:
        embedding = session.get(RetrievalChunkEmbeddingModel, "emb_chunk_rfc_0068_0001")
        assert embedding is not None
        session.delete(embedding)
        session.commit()

    refresh = repository.refresh_index_job("retjob_lotus_platform_rfcs")

    assert refresh is not None
    assert refresh.persisted_embedding_count >= 1


def test_sqlalchemy_retrieval_repository_private_helpers_cover_guard_paths(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-retrieval.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyRetrievalRepository(database_url)

    repository._database_url = "postgresql://stubbed"
    repository._ensure_sqlite_parent_directory()
    repository._register_sqlite_functions()

    repository._database_url = "sqlite:///:memory:"
    repository._ensure_sqlite_parent_directory()

    assert repository._sqlite_vector_score("not-json", "[]") == 0.0
    assert repository._sqlite_vector_score('"bad"', "[]") == 0.0
    assert repository._sqlite_lexical_score("not-json", "title", "preview") == 0.0
    assert repository._sqlite_lexical_score('"bad"', "title", "preview") == 0.0


def test_sqlalchemy_retrieval_repository_creates_parent_directory_for_sqlite_file(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "nested" / "db" / "lotus-ai-retrieval.db"
    database_url = f"sqlite:///{db_path}"

    SqlAlchemyRetrievalRepository(database_url)

    assert db_path.parent.is_dir()
