from __future__ import annotations

from app.config import settings
from app.provider_retention_confirmations.memory_repository import (
    InMemoryProviderRetentionConfirmationRepository,
)
from app.provider_retention_confirmations.repository import (
    ProviderRetentionConfirmationRepository,
)
from app.provider_retention_confirmations.sqlalchemy_repository import (
    SqlAlchemyProviderRetentionConfirmationRepository,
)

_memory_repository = InMemoryProviderRetentionConfirmationRepository()
_sqlalchemy_repository: SqlAlchemyProviderRetentionConfirmationRepository | None = None


def get_provider_retention_confirmation_store() -> ProviderRetentionConfirmationRepository:
    if settings.provider_retention_confirmation_store_mode == "memory":
        return _memory_repository
    if settings.provider_retention_confirmation_store_mode == "sqlalchemy":
        if not settings.database_url:
            raise RuntimeError(
                "LOTUS_AI_DATABASE_URL is required when provider retention confirmation store "
                "mode is sqlalchemy."
            )
        global _sqlalchemy_repository
        if _sqlalchemy_repository is None:
            _sqlalchemy_repository = SqlAlchemyProviderRetentionConfirmationRepository(
                settings.database_url
            )
        return _sqlalchemy_repository
    raise RuntimeError("Unsupported provider retention confirmation store mode.")


def reset_provider_retention_confirmation_store_cache() -> None:
    global _memory_repository
    global _sqlalchemy_repository
    _memory_repository = InMemoryProviderRetentionConfirmationRepository()
    _sqlalchemy_repository = None
