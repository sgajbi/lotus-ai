from pathlib import Path

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
