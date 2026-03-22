from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.contracts.providers import ProviderExecutionMode, ProviderRolloutState
from app.contracts.tasks import CapabilityDescriptor
from app.services.provider_live_execution_state import build_provider_live_execution_state
from app.services.provider_rollout_posture import build_provider_rollout_posture


@dataclass(frozen=True)
class TaskExecutionPathDescriptor:
    execution_path: str
    provider_mode: str
    stubbed: bool
    notes: str


def build_task_execution_path(task: CapabilityDescriptor) -> TaskExecutionPathDescriptor:
    if task.task_id == "knowledge_search.v1":
        return TaskExecutionPathDescriptor(
            execution_path="retrieval.catalog_search",
            provider_mode="catalog_only",
            stubbed=False,
            notes="Bounded retrieval hits from enabled staged approved sources.",
        )
    if task.task_id == "knowledge_answer.v1":
        return TaskExecutionPathDescriptor(
            execution_path="retrieval.catalog_answer",
            provider_mode="catalog_answer",
            stubbed=False,
            notes="Conservative citation-backed answer with explicit refusal on low-support retrieval.",
        )
    return _build_provider_backed_task_execution_path(task=task)


def _build_provider_backed_task_execution_path(
    *, task: CapabilityDescriptor
) -> TaskExecutionPathDescriptor:
    rollout_posture = build_provider_rollout_posture()
    live_execution_state = build_provider_live_execution_state(task_id=task.task_id)
    execution_path = "provider.stub_text"
    notes = rollout_posture.notes
    stubbed = True
    if live_execution_state.live_execution_enabled:
        execution_path = "provider.live_text"
        notes = (
            "Task is allowlisted for governed live text-generation execution through the "
            "provider gateway."
        )
        stubbed = False
    elif (
        settings.provider_mode == ProviderExecutionMode.OPENAI.value
        and live_execution_state.rollout_state
        in {ProviderRolloutState.CANARY_ENABLED, ProviderRolloutState.ROLLED_OUT}
        and not live_execution_state.task_allowlisted
    ):
        execution_path = "provider.task_not_allowlisted"
        notes = live_execution_state.blocking_reason or rollout_posture.notes
    elif settings.provider_mode == ProviderExecutionMode.OPENAI.value:
        execution_path = "provider.blocked_text"
        notes = (
            "Task remains provider-backed, but live-provider execution is still blocked by "
            f"rollout or configuration posture. {rollout_posture.notes} "
            f"{live_execution_state.blocking_reason or ''}"
        )
    elif settings.provider_mode not in {mode.value for mode in ProviderExecutionMode}:
        execution_path = "provider.blocked_text"
        notes = (
            "Task remains provider-backed, but current provider mode is not supported in the "
            "current phase and will be rejected before execution. "
            f"{rollout_posture.notes}"
        )
    return TaskExecutionPathDescriptor(
        execution_path=execution_path,
        provider_mode=settings.provider_mode,
        stubbed=stubbed,
        notes=notes,
    )
