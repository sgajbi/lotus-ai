from __future__ import annotations

from copy import deepcopy

from app.contracts.prompts import (
    PromptDescriptor,
    PromptLifecycleStatus,
    PromptRolloutSelectionMode,
)
from app.prompts.registry import list_prompts
from app.repositories.prompt_repository import PromptRepository
from app.services.prompt_rollout_models import (
    PromptRolloutEventRecord,
    PromptRolloutStateRecord,
)

class InMemoryPromptRepository(PromptRepository):
    def __init__(self) -> None:
        prompts = list_prompts()
        self._prompt_versions = {
            (prompt.task_id, prompt.prompt_version): deepcopy(prompt) for prompt in prompts
        }
        self._rollout_states = {
            prompt.task_id: PromptRolloutStateRecord(
                task_id=prompt.task_id,
                active_prompt_version=prompt.prompt_version,
                candidate_prompt_version=None,
                previous_active_prompt_version=None,
                rollout_mode=PromptRolloutSelectionMode.GOVERNED_CONTROL_ACTIONS,
                runtime_mutation_enabled=True,
            )
            for prompt in prompts
            if prompt.lifecycle_status == PromptLifecycleStatus.ACTIVE
        }
        self._rollout_events: list[PromptRolloutEventRecord] = []

    def list_prompts(self) -> list[PromptDescriptor]:
        prompts = [
            deepcopy(prompt)
            for prompt in self.list_prompt_versions()
            if prompt.lifecycle_status == PromptLifecycleStatus.ACTIVE
        ]
        prompts.sort(key=lambda prompt: prompt.task_id)
        return prompts

    def get_prompt(self, task_id: str) -> PromptDescriptor | None:
        rollout_state = self.get_prompt_rollout_state(task_id)
        if rollout_state is None:
            return None
        return self.get_prompt_version(task_id, rollout_state.active_prompt_version)

    def list_prompt_versions(self) -> list[PromptDescriptor]:
        prompts = [deepcopy(prompt) for prompt in self._prompt_versions.values()]
        prompts.sort(key=lambda prompt: (prompt.task_id, prompt.prompt_version))
        return prompts

    def get_prompt_version(self, task_id: str, prompt_version: str) -> PromptDescriptor | None:
        prompt = self._prompt_versions.get((task_id, prompt_version))
        if prompt is None:
            return None
        return deepcopy(prompt)

    def list_prompt_rollout_states(self) -> list[PromptRolloutStateRecord]:
        states = list(self._rollout_states.values())
        states.sort(key=lambda state: state.task_id)
        return deepcopy(states)

    def get_prompt_rollout_state(self, task_id: str) -> PromptRolloutStateRecord | None:
        state = self._rollout_states.get(task_id)
        if state is None:
            return None
        return deepcopy(state)

    def list_prompt_rollout_events(
        self, task_id: str | None = None
    ) -> list[PromptRolloutEventRecord]:
        events = [
            deepcopy(event)
            for event in self._rollout_events
            if task_id is None or event.task_id == task_id
        ]
        events.sort(key=lambda event: event.recorded_at)
        return events

    def save_prompt_rollout_transition(
        self,
        *,
        rollout_state: PromptRolloutStateRecord,
        updated_prompts: list[PromptDescriptor],
        event: PromptRolloutEventRecord,
    ) -> None:
        self._rollout_states[rollout_state.task_id] = deepcopy(rollout_state)
        for prompt in updated_prompts:
            self._prompt_versions[(prompt.task_id, prompt.prompt_version)] = deepcopy(prompt)
        self._rollout_events.append(deepcopy(event))
