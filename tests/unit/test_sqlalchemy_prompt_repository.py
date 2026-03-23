from pathlib import Path

from app.contracts.prompts import (
    PromptLifecycleStatus,
    PromptManagementMode,
    PromptRolloutSelectionMode,
)
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

    rollout_state = repository.get_prompt_rollout_state("explain.v1")
    assert rollout_state is not None
    assert rollout_state.active_prompt_version == "foundation.explain.v1"
    assert rollout_state.candidate_prompt_version is None
    assert rollout_state.rollout_mode == PromptRolloutSelectionMode.GOVERNED_STATE_READ_ONLY
    assert rollout_state.runtime_mutation_enabled is False

    rollout_events = repository.list_prompt_rollout_events("explain.v1")
    assert rollout_events == []


def test_sqlalchemy_prompt_repository_returns_none_for_unknown_prompt(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'prompt-registry.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyPromptRepository(database_url)

    assert repository.get_prompt("missing.v1") is None
    assert repository.get_prompt_rollout_state("missing.v1") is None


def test_sqlalchemy_prompt_repository_lists_prompt_versions_and_rollout_states(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'prompt-registry.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyPromptRepository(database_url)

    prompt_versions = repository.list_prompt_versions()
    rollout_states = repository.list_prompt_rollout_states()

    assert len(prompt_versions) >= 7
    assert len(rollout_states) >= 7
    explain_state = next(state for state in rollout_states if state.task_id == "explain.v1")
    assert explain_state.active_prompt_version == "foundation.explain.v1"


def test_sqlalchemy_prompt_repository_creates_parent_directory_for_sqlite_file(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "nested" / "db" / "prompt-registry.db"
    database_url = f"sqlite:///{db_path}"

    SqlAlchemyPromptRepository(database_url)

    assert db_path.parent.is_dir()
