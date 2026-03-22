from pathlib import Path

from app.config import settings
from app.repositories.memory_async_runtime_repository import InMemoryAsyncRuntimeRepository
from app.repositories.sqlalchemy_async_runtime_repository import SqlAlchemyAsyncRuntimeRepository
from app.services.async_runtime_store import get_async_runtime_store


def test_async_runtime_store_uses_memory_mode_by_default() -> None:
    settings.async_runtime_store_mode = "memory"

    repository = get_async_runtime_store()

    assert isinstance(repository, InMemoryAsyncRuntimeRepository)


def test_async_runtime_store_uses_sqlalchemy_when_configured(tmp_path: Path) -> None:
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'async-runtime-store.db'}"

    repository = get_async_runtime_store()

    assert isinstance(repository, SqlAlchemyAsyncRuntimeRepository)
