from __future__ import annotations

from app.config import settings
from app.repositories.evaluation_runtime_repository import EvaluationRuntimeRepository
from app.repositories.memory_evaluation_runtime_repository import (
    InMemoryEvaluationRuntimeRepository,
)
from app.repositories.sqlalchemy_evaluation_runtime_repository import (
    SqlAlchemyEvaluationRuntimeRepository,
)

_memory_repository: InMemoryEvaluationRuntimeRepository | None = None
_sqlalchemy_repository: SqlAlchemyEvaluationRuntimeRepository | None = None


def get_evaluation_runtime_store() -> EvaluationRuntimeRepository:
    if settings.evaluation_runtime_store_mode == "memory":
        global _memory_repository
        if _memory_repository is None:
            _memory_repository = InMemoryEvaluationRuntimeRepository()
        return _memory_repository
    if settings.evaluation_runtime_store_mode == "sqlalchemy":
        if not settings.database_url:
            raise RuntimeError(
                "LOTUS_AI_DATABASE_URL is required when LOTUS_AI_EVALUATION_RUNTIME_STORE_MODE=sqlalchemy."
            )
        global _sqlalchemy_repository
        if _sqlalchemy_repository is None:
            _sqlalchemy_repository = SqlAlchemyEvaluationRuntimeRepository(settings.database_url)
        return _sqlalchemy_repository
    raise RuntimeError("Unsupported LOTUS_AI_EVALUATION_RUNTIME_STORE_MODE.")


def reset_evaluation_runtime_store_cache() -> None:
    global _memory_repository
    global _sqlalchemy_repository
    _memory_repository = None
    _sqlalchemy_repository = None

