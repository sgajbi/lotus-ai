from app.contracts.prompts import PromptRolloutSelectionMode
from app.repositories.memory_prompt_repository import InMemoryPromptRepository


def test_memory_prompt_repository_exposes_seeded_versions_and_rollout_state() -> None:
    repository = InMemoryPromptRepository()

    prompts = repository.list_prompt_versions()
    rollout_state = repository.get_prompt_rollout_state("explain.v1")
    prompt = repository.get_prompt("explain.v1")

    assert any(
        item.task_id == "explain.v1" and item.prompt_version == "foundation.explain.v1"
        for item in prompts
    )
    assert any(
        item.task_id == "explain.v1"
        and item.prompt_version == "foundation.explain.v2"
        and item.lifecycle_status.value == "CANDIDATE"
        for item in prompts
    )
    assert rollout_state is not None
    assert rollout_state.active_prompt_version == "foundation.explain.v1"
    assert rollout_state.candidate_prompt_version is None
    assert rollout_state.rollout_mode == PromptRolloutSelectionMode.GOVERNED_CONTROL_ACTIONS
    assert rollout_state.runtime_mutation_enabled is True
    assert prompt is not None
    assert prompt.prompt_version == rollout_state.active_prompt_version


def test_memory_prompt_repository_starts_with_empty_rollout_event_history() -> None:
    repository = InMemoryPromptRepository()

    assert repository.list_prompt_rollout_events() == []
