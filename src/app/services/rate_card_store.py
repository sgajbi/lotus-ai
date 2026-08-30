from __future__ import annotations

from app.config import settings
from app.repositories.memory_rate_card_repository import InMemoryRateCardRepository
from app.repositories.rate_card_repository import RateCardRepository
from app.repositories.sqlalchemy_rate_card_repository import SqlAlchemyRateCardRepository

_memory_repository = InMemoryRateCardRepository()
_sqlalchemy_repository: SqlAlchemyRateCardRepository | None = None


def get_rate_card_repository() -> RateCardRepository:
    if settings.rate_card_store_mode == "memory":
        return _memory_repository
    if settings.rate_card_store_mode == "sqlalchemy":
        if not settings.database_url:
            raise RuntimeError(
                "LOTUS_AI_DATABASE_URL is required when LOTUS_AI_RATE_CARD_STORE_MODE=sqlalchemy."
            )
        global _sqlalchemy_repository
        if _sqlalchemy_repository is None:
            _sqlalchemy_repository = SqlAlchemyRateCardRepository(settings.database_url)
        return _sqlalchemy_repository
    raise RuntimeError("Unsupported LOTUS_AI_RATE_CARD_STORE_MODE.")


def reset_rate_card_store_cache() -> None:
    global _memory_repository
    global _sqlalchemy_repository
    _memory_repository = InMemoryRateCardRepository()
    _sqlalchemy_repository = None
