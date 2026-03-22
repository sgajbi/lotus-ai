from pathlib import Path

from app.contracts.prompts import PromptLifecycleStatus, PromptManagementMode
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
    assert prompt.lifecycle_status == PromptLifecycleStatus.ACTIVE
    assert prompt.management_mode == PromptManagementMode.MIGRATION_MANAGED
    assert prompt.source_reference == "alembic:0003_create_prompt_definitions_table"


def test_sqlalchemy_prompt_repository_returns_none_for_unknown_prompt(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'prompt-registry.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyPromptRepository(database_url)

    assert repository.get_prompt("missing.v1") is None


def test_sqlalchemy_prompt_repository_creates_parent_directory_for_sqlite_file(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "nested" / "db" / "prompt-registry.db"
    database_url = f"sqlite:///{db_path}"

    SqlAlchemyPromptRepository(database_url)

    assert db_path.parent.is_dir()
