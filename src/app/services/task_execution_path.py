from __future__ import annotations

from dataclasses import dataclass

from app.contracts.providers import ProviderExecutionMode, ProviderRolloutState
from app.contracts.tasks import CapabilityDescriptor
from app.services.provider_execution_config import resolve_provider_execution_config
from app.services.provider_live_execution_state import build_provider_live_execution_state
from app.services.provider_rollout_posture import build_provider_rollout_posture
from app.services.retrieval_execution_status import build_retrieval_execution_status


@dataclass(frozen=True)
class TaskExecutionPathDescriptor:
    execution_path: str
    provider_mode: str
    stubbed: bool
    notes: str


def build_task_execution_path(task: CapabilityDescriptor) -> TaskExecutionPathDescriptor:
    if task.task_id == "knowledge_search.v1":
        return _build_retrieval_task_execution_path(task_id=task.task_id)
    if task.task_id == "knowledge_answer.v1":
        return _build_retrieval_task_execution_path(task_id=task.task_id)
    return _build_provider_backed_task_execution_path(task=task)


def _build_retrieval_task_execution_path(*, task_id: str) -> TaskExecutionPathDescriptor:
    retrieval_status = build_retrieval_execution_status()
    if task_id == "knowledge_search.v1":
        if retrieval_status.live_search_enabled:
            return TaskExecutionPathDescriptor(
                execution_path="retrieval.live_search",
                provider_mode="live_search",
                stubbed=False,
                notes="Bounded retrieval hits from the live indexed promoted corpus.",
            )
        return TaskExecutionPathDescriptor(
            execution_path="retrieval.catalog_search",
            provider_mode="catalog_only",
            stubbed=False,
            notes="Bounded retrieval hits from enabled staged approved sources.",
        )
    if retrieval_status.live_search_enabled:
        return TaskExecutionPathDescriptor(
            execution_path="retrieval.live_answer",
            provider_mode="live_answer",
            stubbed=False,
            notes="Conservative citation-backed answer over the live indexed promoted corpus.",
        )
    return TaskExecutionPathDescriptor(
        execution_path="retrieval.catalog_answer",
        provider_mode="catalog_answer",
        stubbed=False,
        notes="Conservative citation-backed answer with explicit refusal on low-support retrieval.",
    )


def _build_provider_backed_task_execution_path(
    *, task: CapabilityDescriptor
) -> TaskExecutionPathDescriptor:
    provider_mode = resolve_provider_execution_config().provider_mode
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
        provider_mode
        in {
            ProviderExecutionMode.OPENAI.value,
            ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE.value,
        }
        and live_execution_state.rollout_state
        in {ProviderRolloutState.CANARY_ENABLED, ProviderRolloutState.ROLLED_OUT}
        and not live_execution_state.task_allowlisted
    ):
        execution_path = "provider.task_not_allowlisted"
        notes = live_execution_state.blocking_reason or rollout_posture.notes
    elif provider_mode in {
        ProviderExecutionMode.OPENAI.value,
        ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE.value,
    }:
        execution_path = "provider.blocked_text"
        notes = (
            "Task remains provider-backed, but live-provider execution is still blocked by "
            f"rollout or configuration posture. {rollout_posture.notes} "
            f"{live_execution_state.blocking_reason or ''}"
        )
    elif provider_mode not in {
        ProviderExecutionMode.DISABLED.value,
        ProviderExecutionMode.STUB.value,
        ProviderExecutionMode.OPENAI.value,
        ProviderExecutionMode.LOCAL_OPENAI_COMPATIBLE.value,
    }:
        execution_path = "provider.blocked_text"
        notes = (
            "Task remains provider-backed, but current provider mode is not supported in the "
            "current phase and will be rejected before execution. "
            f"{rollout_posture.notes}"
        )
    return TaskExecutionPathDescriptor(
        execution_path=execution_path,
        provider_mode=provider_mode,
        stubbed=stubbed,
        notes=notes,
    )
