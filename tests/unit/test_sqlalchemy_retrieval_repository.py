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
