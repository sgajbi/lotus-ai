from __future__ import annotations

from app.config import settings
from app.repositories.async_runtime_repository import AsyncRuntimeRepository
from app.repositories.memory_async_runtime_repository import InMemoryAsyncRuntimeRepository
from app.repositories.sqlalchemy_async_runtime_repository import SqlAlchemyAsyncRuntimeRepository

_memory_repository: InMemoryAsyncRuntimeRepository | None = None
_sqlalchemy_repository: SqlAlchemyAsyncRuntimeRepository | None = None


def get_async_runtime_store() -> AsyncRuntimeRepository:
    if settings.async_runtime_store_mode == "memory":
        global _memory_repository
        if _memory_repository is None:
            _memory_repository = InMemoryAsyncRuntimeRepository()
        return _memory_repository
    if settings.async_runtime_store_mode == "sqlalchemy":
        if not settings.database_url:
            raise RuntimeError(
                "LOTUS_AI_DATABASE_URL is required when LOTUS_AI_ASYNC_RUNTIME_STORE_MODE=sqlalchemy."
            )
        global _sqlalchemy_repository
        if _sqlalchemy_repository is None:
            _sqlalchemy_repository = SqlAlchemyAsyncRuntimeRepository(settings.database_url)
        return _sqlalchemy_repository
    raise RuntimeError("Unsupported LOTUS_AI_ASYNC_RUNTIME_STORE_MODE.")


def reset_async_runtime_store_cache() -> None:
    global _memory_repository
    global _sqlalchemy_repository
    _memory_repository = None
    _sqlalchemy_repository = None
