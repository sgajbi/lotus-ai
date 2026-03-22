from pathlib import Path

from app.config import settings
from app.repositories.memory_retrieval_repository import InMemoryRetrievalRepository
from app.repositories.sqlalchemy_retrieval_repository import SqlAlchemyRetrievalRepository
from app.services.retrieval_store import get_retrieval_repository, reset_retrieval_repository
from tests.support.migration_runner import upgrade_database_to_head


def test_get_retrieval_repository_returns_memory_repository_by_default() -> None:
    settings.retrieval_store_mode = "memory"
    reset_retrieval_repository()

    repository = get_retrieval_repository()

    assert isinstance(repository, InMemoryRetrievalRepository)


def test_get_retrieval_repository_returns_sqlalchemy_repository(tmp_path: Path) -> None:
    settings.retrieval_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'factory-retrieval.db'}"
    upgrade_database_to_head(settings.database_url)
    reset_retrieval_repository()

    repository = get_retrieval_repository()

    assert isinstance(repository, SqlAlchemyRetrievalRepository)

    settings.retrieval_store_mode = "memory"
    settings.database_url = None
    reset_retrieval_repository()
