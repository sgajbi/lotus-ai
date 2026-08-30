from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from app.config import settings
from app.repositories.memory_provider_operations_repository import (
    InMemoryProviderOperationsRepository,
)
from app.repositories.provider_operations_repository import ProviderOperationsRepository
from app.repositories.sqlalchemy_provider_operations_repository import (
    SqlAlchemyProviderOperationsRepository,
)

_memory_repository: InMemoryProviderOperationsRepository | None = None
_sqlalchemy_repository: SqlAlchemyProviderOperationsRepository | None = None

_store_mode_override: ContextVar[str | None] = ContextVar(
    "lotus_ai_provider_operations_store_mode_override", default=None
)


@contextmanager
def override_provider_operations_store_mode(mode: str) -> Iterator[None]:
    """Execution-scoped store-mode override (issue #148, S4).

    Used by the evaluation runtime to run a case against the durable store
    without mutating process settings; both backend caches coexist, so a
    concurrent production request keeps its configured backend.
    """

    token = _store_mode_override.set(mode)
    try:
        yield
    finally:
        _store_mode_override.reset(token)


def resolved_provider_operations_store_mode() -> str:
    return _store_mode_override.get() or settings.provider_operations_store_mode


def get_provider_operations_store() -> ProviderOperationsRepository:
    if resolved_provider_operations_store_mode() == "memory":
        global _memory_repository
        if _memory_repository is None:
            _memory_repository = InMemoryProviderOperationsRepository()
        return _memory_repository
    if resolved_provider_operations_store_mode() == "sqlalchemy":
        if not settings.database_url:
            raise RuntimeError(
                "LOTUS_AI_DATABASE_URL is required when LOTUS_AI_PROVIDER_OPERATIONS_STORE_MODE=sqlalchemy."
            )
        global _sqlalchemy_repository
        if _sqlalchemy_repository is None:
            _sqlalchemy_repository = SqlAlchemyProviderOperationsRepository(settings.database_url)
        return _sqlalchemy_repository
    raise RuntimeError("Unsupported LOTUS_AI_PROVIDER_OPERATIONS_STORE_MODE.")


def reset_provider_operations_store_cache() -> None:
    global _memory_repository
    global _sqlalchemy_repository
    _memory_repository = None
    _sqlalchemy_repository = None
