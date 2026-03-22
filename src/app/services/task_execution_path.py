from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.contracts.tasks import CapabilityDescriptor


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
    execution_path = "provider.stub_text"
    notes = "Foundation-phase deterministic stub path through the provider gateway."
    if settings.provider_mode not in {"disabled", "stub"}:
        execution_path = "provider.blocked_text"
        notes = (
            "Task remains provider-backed, but current provider mode is not supported in the "
            "current phase and will be rejected before execution."
        )
    return TaskExecutionPathDescriptor(
        execution_path=execution_path,
        provider_mode=settings.provider_mode,
        stubbed=True,
        notes=notes,
    )
