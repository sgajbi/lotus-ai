from __future__ import annotations

from app.config import settings
from app.repositories.memory_provider_operations_repository import (
    InMemoryProviderOperationsRepository,
)
from app.repositories.provider_operations_repository import ProviderOperationsRepository
from app.repositories.sqlalchemy_provider_operations_repository import (
    SqlAlchemyProviderOperationsRepository,
)

_memory_repository = InMemoryProviderOperationsRepository()
_sqlalchemy_repository: SqlAlchemyProviderOperationsRepository | None = None


def get_provider_operations_store() -> ProviderOperationsRepository:
    if settings.provider_operations_store_mode == "memory":
        return _memory_repository
    if settings.provider_operations_store_mode == "sqlalchemy":
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
    global _sqlalchemy_repository
    _sqlalchemy_repository = None
