from __future__ import annotations

from app.config import settings
from app.repositories.memory_retrieval_repository import InMemoryRetrievalRepository
from app.repositories.retrieval_repository import RetrievalRepository
from app.repositories.sqlalchemy_retrieval_repository import SqlAlchemyRetrievalRepository

_retrieval_repository: RetrievalRepository | None = None
_sqlalchemy_retrieval_repository: SqlAlchemyRetrievalRepository | None = None


def get_retrieval_repository() -> RetrievalRepository:
    global _retrieval_repository
    if settings.retrieval_store_mode == "memory":
        if _retrieval_repository is None:
            _retrieval_repository = InMemoryRetrievalRepository()
        return _retrieval_repository
    if settings.retrieval_store_mode == "sqlalchemy":
        if not settings.database_url:
            raise RuntimeError(
                "LOTUS_AI_DATABASE_URL is required when LOTUS_AI_RETRIEVAL_STORE_MODE=sqlalchemy."
            )
        global _sqlalchemy_retrieval_repository
        if _sqlalchemy_retrieval_repository is None:
            _sqlalchemy_retrieval_repository = SqlAlchemyRetrievalRepository(settings.database_url)
        return _sqlalchemy_retrieval_repository
    raise RuntimeError("Unsupported LOTUS_AI_RETRIEVAL_STORE_MODE.")


def reset_retrieval_repository() -> None:
    global _retrieval_repository
    global _sqlalchemy_retrieval_repository
    _retrieval_repository = None
    _sqlalchemy_retrieval_repository = None
