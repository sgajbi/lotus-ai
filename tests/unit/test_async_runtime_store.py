from pathlib import Path

import pytest

from app.config import settings
from app.repositories.memory_async_runtime_repository import InMemoryAsyncRuntimeRepository
from app.repositories.sqlalchemy_async_runtime_repository import SqlAlchemyAsyncRuntimeRepository
from app.services.async_runtime_store import (
    get_async_runtime_store,
    reset_async_runtime_store_cache,
)


def test_async_runtime_store_uses_memory_mode_by_default() -> None:
    settings.async_runtime_store_mode = "memory"

    repository = get_async_runtime_store()

    assert isinstance(repository, InMemoryAsyncRuntimeRepository)


def test_async_runtime_store_uses_sqlalchemy_when_configured(tmp_path: Path) -> None:
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'async-runtime-store.db'}"

    repository = get_async_runtime_store()

    assert isinstance(repository, SqlAlchemyAsyncRuntimeRepository)


def test_async_runtime_store_requires_database_url_for_sqlalchemy_mode() -> None:
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.database_url = None
    reset_async_runtime_store_cache()

    with pytest.raises(RuntimeError) as exc_info:
        get_async_runtime_store()

    assert "LOTUS_AI_DATABASE_URL is required" in str(exc_info.value)


def test_async_runtime_store_rejects_unsupported_mode() -> None:
    settings.async_runtime_store_mode = "unsupported"
    reset_async_runtime_store_cache()

    with pytest.raises(RuntimeError) as exc_info:
        get_async_runtime_store()

    assert "Unsupported LOTUS_AI_ASYNC_RUNTIME_STORE_MODE" in str(exc_info.value)
