from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch
from sqlalchemy import event

from app.contracts.retrieval import (
    RetrievalDocumentVersionDescriptor,
    RetrievalDocumentVersionLifecycleStatus,
    RetrievalIngestionAction,
    RetrievalIngestionJobDescriptor,
    RetrievalIngestionJobStatus,
    RetrievalJobStatus,
)
from app.repositories.sqlalchemy_retrieval_repository import (
    SqlAlchemyRetrievalRepository,
    _search_candidate_window,
)
from tests.support.migration_runner import upgrade_database_to_head


def test_sqlalchemy_retrieval_repository_returns_seeded_catalog(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-retrieval.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyRetrievalRepository(database_url)

    sources = repository.list_sources()
    documents = repository.list_documents_for_source("lotus-platform-rfcs")
    chunks = repository.list_chunks_for_document("lotus-platform-rfc-0069")
    job = repository.get_index_job("retjob_lotus_platform_rfcs")
    versions = repository.list_document_versions()
    ingestion_jobs = repository.list_ingestion_jobs()

    assert any(source.source_id == "lotus-platform-rfcs" for source in sources)
    assert any(document.document_id == "lotus-platform-rfc-0069" for document in documents)
    assert any(chunk.chunk_id == "chunk_rfc_0069_0001" for chunk in chunks)
    assert job is not None
    assert job.source_id == "lotus-platform-rfcs"
    assert any(version.lifecycle_status == "SUPERSEDED" for version in versions)
    assert any(job.status == "BLOCKED" for job in ingestion_jobs)


def test_sqlalchemy_retrieval_repository_returns_none_for_unknown_records(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-retrieval.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyRetrievalRepository(database_url)

    assert repository.get_source("missing-source") is None
    assert repository.get_document("missing-document") is None
    assert repository.get_index_job("missing-job") is None
    assert repository.get_ingestion_job("missing-job") is None
    assert repository.list_documents_for_source("missing-source") == []
    assert repository.list_chunks_for_document("missing-document") == []


def test_sqlalchemy_retrieval_repository_creates_parent_directory_for_sqlite_file(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "nested" / "db" / "lotus-ai-retrieval.db"
    database_url = f"sqlite:///{db_path}"

    SqlAlchemyRetrievalRepository(database_url)

    assert db_path.parent.is_dir()


def test_sqlalchemy_retrieval_repository_leaves_memory_sqlite_without_directory_work(
    tmp_path: Path,
) -> None:
    repository = SqlAlchemyRetrievalRepository("sqlite:///:memory:")

    assert repository is not None


def test_sqlalchemy_retrieval_repository_handles_relative_sqlite_path(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    relative_db = Path("tmp") / "nested" / "lotus-ai-relative.db"
    monkeypatch.chdir(tmp_path)

    SqlAlchemyRetrievalRepository(f"sqlite:///{relative_db}")

    assert (tmp_path / "tmp" / "nested").is_dir()


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


def test_sqlalchemy_retrieval_repository_persists_document_version_and_ingestion_job_state(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-retrieval.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyRetrievalRepository(database_url)

    repository.save_document_version(
        RetrievalDocumentVersionDescriptor(
            version_id="ver_test_refresh",
            document_id="lotus-ai-system-overview",
            source_id="lotus-ai-architecture",
            title="lotus-ai System Overview",
            location="lotus-ai/docs/architecture/system-overview.md",
            lifecycle_status=RetrievalDocumentVersionLifecycleStatus.ACTIVE,
            refresh_action=RetrievalIngestionAction.REFRESH,
            lineage_parent_version_id="ver_lotus_ai_system_overview_2026_03_22",
            created_at="2026-03-24T01:00:00Z",
            created_by="operator-a",
            notes="Latest active refresh seed.",
        )
    )
    repository.save_ingestion_job(
        RetrievalIngestionJobDescriptor(
            job_id="ingjob_test_refresh",
            source_id="lotus-ai-architecture",
            document_id="lotus-ai-system-overview",
            target_version_id="ver_test_refresh",
            requested_action=RetrievalIngestionAction.REFRESH,
            status=RetrievalIngestionJobStatus.STAGED,
            requested_by="operator-a",
            requested_at="2026-03-24T01:00:00Z",
            message="Recorded for later runtime execution.",
        )
    )

    restarted_repository = SqlAlchemyRetrievalRepository(database_url)
    versions = restarted_repository.list_document_versions()
    ingestion_jobs = restarted_repository.list_ingestion_jobs()

    assert versions[0].version_id == "ver_test_refresh"
    assert ingestion_jobs[0].job_id == "ingjob_test_refresh"


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
    assert hits[0].document_location is not None
    assert hits[0].active_version_id == "ver_lotus_platform_rfc_0069_2026_03_22"
    assert hits[0].citation_ref is not None


def test_sqlalchemy_retrieval_repository_bounds_search_before_metadata_loading(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-retrieval.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyRetrievalRepository(database_url)
    repository.set_source_index_status(
        source_id="lotus-platform-rfcs",
        index_status="INDEXED",
    )
    statements: list[str] = []

    def capture_statement(
        _conn: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: object,
    ) -> None:
        statements.append(statement)

    event.listen(repository._engine, "before_cursor_execute", capture_statement)
    try:
        hits = repository.search_indexed_chunks(
            query="shared ai platform service",
            source_ids=["lotus-platform-rfcs"],
            limit=1,
        )
    finally:
        event.remove(repository._engine, "before_cursor_execute", capture_statement)

    assert hits
    assert _search_candidate_window(1) == 50
    candidate_queries = [
        statement
        for statement in statements
        if "retrieval_chunks" in statement and "JOIN retrieval_documents" in statement
    ]
    version_queries = [
        statement for statement in statements if "FROM retrieval_document_versions" in statement
    ]
    ingestion_queries = [
        statement for statement in statements if "FROM retrieval_ingestion_jobs" in statement
    ]
    assert len(candidate_queries) == 1
    assert "LIMIT" in candidate_queries[0]
    assert len(version_queries) == 1
    assert len(ingestion_queries) == 1


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


def test_sqlalchemy_retrieval_repository_returns_no_hits_for_unmatched_indexed_query(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-retrieval.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyRetrievalRepository(database_url)
    repository.set_source_index_status(
        source_id="lotus-platform-rfcs",
        index_status="INDEXED",
    )

    hits = repository.search_indexed_chunks(
        query="zzzxqv unmatched phrase",
        source_ids=["lotus-platform-rfcs"],
        limit=5,
    )

    assert hits == []
