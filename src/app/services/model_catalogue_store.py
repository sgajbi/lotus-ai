from __future__ import annotations

from app.config import settings
from app.repositories.memory_model_catalogue_repository import InMemoryModelCatalogueRepository
from app.repositories.model_catalogue_repository import ModelCatalogueRepository
from app.repositories.sqlalchemy_model_catalogue_repository import (
    SqlAlchemyModelCatalogueRepository,
)

_memory_repository = InMemoryModelCatalogueRepository()
_sqlalchemy_repository: SqlAlchemyModelCatalogueRepository | None = None


def get_model_catalogue_repository() -> ModelCatalogueRepository:
    if settings.model_catalogue_store_mode == "memory":
        return _memory_repository
    if settings.model_catalogue_store_mode == "sqlalchemy":
        if not settings.database_url:
            raise RuntimeError(
                "LOTUS_AI_DATABASE_URL is required when LOTUS_AI_MODEL_CATALOGUE_STORE_MODE=sqlalchemy."
            )
        global _sqlalchemy_repository
        if _sqlalchemy_repository is None:
            _sqlalchemy_repository = SqlAlchemyModelCatalogueRepository(settings.database_url)
        return _sqlalchemy_repository
    raise RuntimeError("Unsupported LOTUS_AI_MODEL_CATALOGUE_STORE_MODE.")


def reset_model_catalogue_store_cache() -> None:
    global _memory_repository
    global _sqlalchemy_repository
    _memory_repository = InMemoryModelCatalogueRepository()
    _sqlalchemy_repository = None
