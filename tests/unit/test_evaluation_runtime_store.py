from pathlib import Path

import pytest

from app.config import settings
from app.repositories.memory_evaluation_runtime_repository import (
    InMemoryEvaluationRuntimeRepository,
)
from app.repositories.sqlalchemy_evaluation_runtime_repository import (
    SqlAlchemyEvaluationRuntimeRepository,
)
from app.services.evaluation_runtime_store import (
    get_evaluation_runtime_store,
    reset_evaluation_runtime_store_cache,
)


def test_evaluation_runtime_store_returns_cached_memory_repository() -> None:
    settings.evaluation_runtime_store_mode = "memory"

    first = get_evaluation_runtime_store()
    second = get_evaluation_runtime_store()

    assert isinstance(first, InMemoryEvaluationRuntimeRepository)
    assert first is second


def test_evaluation_runtime_store_returns_cached_sqlalchemy_repository(
    tmp_path: Path,
) -> None:
    settings.evaluation_runtime_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-eval-runtime.db'}"

    first = get_evaluation_runtime_store()
    second = get_evaluation_runtime_store()

    assert isinstance(first, SqlAlchemyEvaluationRuntimeRepository)
    assert first is second


def test_evaluation_runtime_store_requires_database_url_for_sqlalchemy_mode() -> None:
    settings.evaluation_runtime_store_mode = "sqlalchemy"
    settings.database_url = None

    reset_evaluation_runtime_store_cache()

    with pytest.raises(RuntimeError, match="LOTUS_AI_DATABASE_URL is required"):
        get_evaluation_runtime_store()


def test_evaluation_runtime_store_rejects_unsupported_mode() -> None:
    settings.evaluation_runtime_store_mode = "unsupported"

    reset_evaluation_runtime_store_cache()

    with pytest.raises(RuntimeError, match="Unsupported"):
        get_evaluation_runtime_store()
