from pathlib import Path

from app.contracts.retrieval import RetrievalJobStatus
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
    assert any(document.document_id == "lotus-platform-rfc-0069" for document in documents)
    assert any(chunk.chunk_id == "chunk_rfc_0069_0001" for chunk in chunks)
    assert job is not None
    assert job.source_id == "lotus-platform-rfcs"


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


def test_sqlalchemy_retrieval_repository_creates_parent_directory_for_sqlite_file(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "nested" / "db" / "lotus-ai-retrieval.db"
    database_url = f"sqlite:///{db_path}"

    SqlAlchemyRetrievalRepository(database_url)

    assert db_path.parent.is_dir()


def test_sqlalchemy_retrieval_repository_updates_jobs_and_index_status(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-retrieval.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyRetrievalRepository(database_url)

    assert repository.list_source_ids()
    assert repository.get_source("lotus-platform-rfcs") is not None
    assert repository.get_document("lotus-platform-rfc-0069") is not None

    existing_job = repository.get_index_job("retjob_lotus_platform_rfcs")
    assert existing_job is not None
    repository.save_index_job(
        existing_job.model_copy(
            update={
                "status": RetrievalJobStatus.COMPLETED,
                "message": "Runtime-backed retrieval indexing completed.",
            }
        )
    )
    repository.set_source_index_status(
        source_id="lotus-platform-rfcs",
        index_status="INDEXED",
    )

    job = repository.get_index_job("retjob_lotus_platform_rfcs")
    documents = repository.list_documents_for_source("lotus-platform-rfcs")
    chunks = repository.list_chunks_for_document("lotus-platform-rfc-0069")

    assert job is not None
    assert job.status == "COMPLETED"
    assert all(document.index_status == "INDEXED" for document in documents)
    assert all(chunk.index_status == "INDEXED" for chunk in chunks)


def test_sqlalchemy_retrieval_repository_searches_indexed_chunks(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-retrieval.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyRetrievalRepository(database_url)
    repository.set_source_index_status(
        source_id="lotus-platform-rfcs",
        index_status="INDEXED",
    )

    hits = repository.search_indexed_chunks(
        query="shared ai platform service",
        source_ids=["lotus-platform-rfcs"],
        limit=5,
    )

    assert hits
    assert hits[0].source_id == "lotus-platform-rfcs"
    assert hits[0].document_id == "lotus-platform-rfc-0069"
    assert hits[0].chunk_id == "chunk_rfc_0069_0001"


def test_sqlalchemy_retrieval_repository_preserves_live_search_state_across_restart_and_rollback(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-retrieval.db'}"
    upgrade_database_to_head(database_url)

    repository = SqlAlchemyRetrievalRepository(database_url)
    repository.set_source_index_status(
        source_id="lotus-platform-rfcs",
        index_status="INDEXED",
    )

    initial_hits = repository.search_indexed_chunks(
        query="shared ai platform service",
        source_ids=["lotus-platform-rfcs"],
        limit=5,
    )
    restarted_repository = SqlAlchemyRetrievalRepository(database_url)
    restarted_hits = restarted_repository.search_indexed_chunks(
        query="shared ai platform service",
        source_ids=["lotus-platform-rfcs"],
        limit=5,
    )

    assert initial_hits
    assert restarted_hits
    assert restarted_hits[0].chunk_id == "chunk_rfc_0069_0001"

    restarted_repository.set_source_index_status(
        source_id="lotus-platform-rfcs",
        index_status="STAGED",
    )
    rolled_back_repository = SqlAlchemyRetrievalRepository(database_url)
    rolled_back_hits = rolled_back_repository.search_indexed_chunks(
        query="shared ai platform service",
        source_ids=["lotus-platform-rfcs"],
        limit=5,
    )

    assert rolled_back_hits == []
