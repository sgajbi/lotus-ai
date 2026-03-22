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
