import os
from pathlib import Path

from app.contracts.prompts import (
    PromptControlActionType,
    PromptLifecycleStatus,
    PromptManagementMode,
    PromptRolloutSelectionMode,
)
from app.repositories.sqlalchemy_prompt_repository import SqlAlchemyPromptRepository
from app.services.prompt_rollout_models import PromptRolloutEventRecord, PromptRolloutStateRecord
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
    assert rollout_state.rollout_mode == PromptRolloutSelectionMode.GOVERNED_CONTROL_ACTIONS
    assert rollout_state.runtime_mutation_enabled is True

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

    assert len(prompt_versions) >= 9
    assert len(rollout_states) >= 7
    explain_state = next(state for state in rollout_states if state.task_id == "explain.v1")
    assert explain_state.active_prompt_version == "foundation.explain.v1"
    assert any(
        prompt.task_id == "explain.v1"
        and prompt.prompt_version == "foundation.explain.v2"
        and prompt.lifecycle_status == PromptLifecycleStatus.CANDIDATE
        for prompt in prompt_versions
    )


def test_sqlalchemy_prompt_repository_saves_rollout_transition_and_event(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'prompt-registry.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyPromptRepository(database_url)

    promoted_prompt = repository.get_prompt_version("explain.v1", "foundation.explain.v2")
    retired_prompt = repository.get_prompt_version("explain.v1", "foundation.explain.v1")
    assert promoted_prompt is not None
    assert retired_prompt is not None

    repository.save_prompt_rollout_transition(
        rollout_state=PromptRolloutStateRecord(
            task_id="explain.v1",
            active_prompt_version="foundation.explain.v2",
            candidate_prompt_version=None,
            previous_active_prompt_version="foundation.explain.v1",
            rollout_mode=PromptRolloutSelectionMode.GOVERNED_CONTROL_ACTIONS,
            runtime_mutation_enabled=True,
        ),
        updated_prompts=[
            retired_prompt.model_copy(update={"lifecycle_status": PromptLifecycleStatus.RETIRED}),
            promoted_prompt.model_copy(update={"lifecycle_status": PromptLifecycleStatus.ACTIVE}),
        ],
        event=PromptRolloutEventRecord(
            event_id="prompt_evt_test_promote",
            task_id="explain.v1",
            action_type=PromptControlActionType.PROMOTE_CANDIDATE,
            requested_by="alice@lotus.test",
            approved_by="bob@lotus.test",
            reason="Promote candidate",
            prior_active_prompt_version="foundation.explain.v1",
            resulting_active_prompt_version="foundation.explain.v2",
            prior_candidate_prompt_version=None,
            resulting_candidate_prompt_version=None,
            recorded_at="2026-03-23T09:00:00Z",
        ),
    )

    rollout_state = repository.get_prompt_rollout_state("explain.v1")
    rollout_events = repository.list_prompt_rollout_events("explain.v1")
    active_prompt = repository.get_prompt("explain.v1")

    assert rollout_state is not None
    assert rollout_state.active_prompt_version == "foundation.explain.v2"
    assert rollout_state.previous_active_prompt_version == "foundation.explain.v1"
    assert active_prompt is not None
    assert active_prompt.prompt_version == "foundation.explain.v2"
    assert rollout_events[-1].action_type == PromptControlActionType.PROMOTE_CANDIDATE


def test_sqlalchemy_prompt_repository_creates_parent_directory_for_sqlite_file(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "nested" / "db" / "prompt-registry.db"
    database_url = f"sqlite:///{db_path}"

    SqlAlchemyPromptRepository(database_url)

    assert db_path.parent.is_dir()


def test_sqlalchemy_prompt_repository_returns_none_for_unknown_prompt_version(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'prompt-registry.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyPromptRepository(database_url)

    assert repository.get_prompt_version("explain.v1", "missing.version") is None


def test_sqlalchemy_prompt_repository_rejects_transition_with_missing_prompt_version(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'prompt-registry.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyPromptRepository(database_url)
    active_prompt = repository.get_prompt_version("explain.v1", "foundation.explain.v1")
    assert active_prompt is not None

    try:
        repository.save_prompt_rollout_transition(
            rollout_state=PromptRolloutStateRecord(
                task_id="explain.v1",
                active_prompt_version="foundation.explain.v1",
                candidate_prompt_version=None,
                previous_active_prompt_version=None,
                rollout_mode=PromptRolloutSelectionMode.GOVERNED_CONTROL_ACTIONS,
                runtime_mutation_enabled=True,
            ),
            updated_prompts=[
                active_prompt.model_copy(update={"prompt_version": "missing.version"}),
            ],
            event=PromptRolloutEventRecord(
                event_id="prompt_evt_missing_prompt",
                task_id="explain.v1",
                action_type=PromptControlActionType.PROMOTE_CANDIDATE,
                requested_by="alice@lotus.test",
                approved_by="bob@lotus.test",
                reason="Exercise missing prompt transition branch",
                prior_active_prompt_version="foundation.explain.v1",
                resulting_active_prompt_version="foundation.explain.v1",
                prior_candidate_prompt_version=None,
                resulting_candidate_prompt_version=None,
                recorded_at="2026-03-24T09:00:00Z",
            ),
        )
    except RuntimeError as exc:
        assert "missing prompt definition version" in str(exc)
    else:
        raise AssertionError("Expected missing prompt definition version to fail")


def test_sqlalchemy_prompt_repository_rejects_transition_with_missing_rollout_state(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'prompt-registry.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyPromptRepository(database_url)
    active_prompt = repository.get_prompt_version("explain.v1", "foundation.explain.v1")
    assert active_prompt is not None

    try:
        repository.save_prompt_rollout_transition(
            rollout_state=PromptRolloutStateRecord(
                task_id="missing.v1",
                active_prompt_version="foundation.explain.v1",
                candidate_prompt_version=None,
                previous_active_prompt_version=None,
                rollout_mode=PromptRolloutSelectionMode.GOVERNED_CONTROL_ACTIONS,
                runtime_mutation_enabled=True,
            ),
            updated_prompts=[active_prompt],
            event=PromptRolloutEventRecord(
                event_id="prompt_evt_missing_state",
                task_id="missing.v1",
                action_type=PromptControlActionType.PROMOTE_CANDIDATE,
                requested_by="alice@lotus.test",
                approved_by="bob@lotus.test",
                reason="Exercise missing rollout state branch",
                prior_active_prompt_version="foundation.explain.v1",
                resulting_active_prompt_version="foundation.explain.v1",
                prior_candidate_prompt_version=None,
                resulting_candidate_prompt_version=None,
                recorded_at="2026-03-24T09:00:00Z",
            ),
        )
    except RuntimeError as exc:
        assert "missing rollout state" in str(exc)
    else:
        raise AssertionError("Expected missing rollout state to fail")


def test_sqlalchemy_prompt_repository_accepts_memory_and_relative_sqlite_urls(
    tmp_path: Path,
) -> None:
    SqlAlchemyPromptRepository("sqlite:///:memory:")

    previous_cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        SqlAlchemyPromptRepository("sqlite:///relative/prompt-registry.db")
        assert (tmp_path / "relative").is_dir()
    finally:
        os.chdir(previous_cwd)
