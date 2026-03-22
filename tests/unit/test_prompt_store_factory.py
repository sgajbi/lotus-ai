from pathlib import Path

from app.config import settings
from app.repositories.memory_prompt_repository import InMemoryPromptRepository
from app.repositories.sqlalchemy_prompt_repository import SqlAlchemyPromptRepository
from app.services.prompt_store import get_prompt_repository, reset_prompt_store_cache
from tests.support.migration_runner import upgrade_database_to_head


def test_get_prompt_repository_returns_memory_repository_by_default() -> None:
    settings.prompt_store_mode = "memory"
    reset_prompt_store_cache()

    repository = get_prompt_repository()

    assert isinstance(repository, InMemoryPromptRepository)


def test_get_prompt_repository_returns_sqlalchemy_repository(tmp_path: Path) -> None:
    settings.prompt_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'factory-prompts.db'}"
    upgrade_database_to_head(settings.database_url)
    reset_prompt_store_cache()

    repository = get_prompt_repository()

    assert isinstance(repository, SqlAlchemyPromptRepository)

    settings.prompt_store_mode = "memory"
    settings.database_url = None
    reset_prompt_store_cache()


def test_get_prompt_repository_rejects_sqlalchemy_mode_without_database_url() -> None:
    settings.prompt_store_mode = "sqlalchemy"
    settings.database_url = None
    reset_prompt_store_cache()

    try:
        get_prompt_repository()
    except RuntimeError as exc:
        assert "LOTUS_AI_DATABASE_URL is required" in str(exc)
    else:
        raise AssertionError(
            "Expected RuntimeError when sqlalchemy prompt store has no database URL"
        )

    settings.prompt_store_mode = "memory"
    reset_prompt_store_cache()


def test_get_prompt_repository_rejects_unsupported_mode() -> None:
    settings.prompt_store_mode = "unsupported"
    reset_prompt_store_cache()

    try:
        get_prompt_repository()
    except RuntimeError as exc:
        assert "Unsupported LOTUS_AI_PROMPT_STORE_MODE" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for unsupported prompt store mode")

    settings.prompt_store_mode = "memory"
    reset_prompt_store_cache()
