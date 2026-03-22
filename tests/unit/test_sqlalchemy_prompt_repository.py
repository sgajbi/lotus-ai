from pathlib import Path

from app.repositories.sqlalchemy_prompt_repository import SqlAlchemyPromptRepository
from tests.support.migration_runner import upgrade_database_to_head


def test_sqlalchemy_prompt_repository_returns_seeded_prompts(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'prompt-registry.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyPromptRepository(database_url)

    prompts = repository.list_prompts()
    prompt = repository.get_prompt("explain.v1")

    assert any(item.task_id == "explain.v1" for item in prompts)
    assert prompt is not None
    assert prompt.prompt_version == "foundation.explain.v1"
