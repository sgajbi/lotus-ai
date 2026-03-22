from __future__ import annotations

from app.config import settings
from app.contracts.task_runtime import (
    TaskRuntimeCategorySummary,
    TaskRuntimeDescriptor,
    TaskRuntimeStatusResponse,
)
from app.contracts.tasks import CapabilityDescriptor, OutputLabel, TaskCategory
from app.services.capability_catalog import build_capability_catalog


def build_task_runtime_status() -> TaskRuntimeStatusResponse:
    catalog = build_capability_catalog()
    task_descriptors = [_build_task_descriptor(task=task) for task in catalog.tasks]
    categories = [
        _build_category_summary(category=category, tasks=task_descriptors)
        for category in TaskCategory
        if any(task.category == category for task in task_descriptors)
    ]
    enabled_tasks = [task for task in task_descriptors if task.enabled]
    return TaskRuntimeStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        enabled_task_count=len(enabled_tasks),
        stubbed_task_count=sum(1 for task in enabled_tasks if task.stubbed),
        retrieval_backed_task_count=sum(
            1 for task in enabled_tasks if task.execution_path.startswith("retrieval")
        ),
        categories=categories,
        tasks=task_descriptors,
    )


def _build_task_descriptor(*, task: CapabilityDescriptor) -> TaskRuntimeDescriptor:
    if task.task_id == "knowledge_search.v1":
        return TaskRuntimeDescriptor(
            task_id=task.task_id,
            category=TaskCategory.KNOWLEDGE_SEARCH,
            enabled=True,
            output_label=OutputLabel.RETRIEVAL_ANSWER,
            execution_path="retrieval.catalog_search",
            provider_mode="catalog_only",
            stubbed=False,
            notes="Bounded retrieval hits from enabled staged approved sources.",
        )
    if task.task_id == "knowledge_answer.v1":
        return TaskRuntimeDescriptor(
            task_id=task.task_id,
            category=TaskCategory.KNOWLEDGE_ANSWER,
            enabled=True,
            output_label=OutputLabel.RETRIEVAL_ANSWER,
            execution_path="retrieval.catalog_answer",
            provider_mode="catalog_answer",
            stubbed=False,
            notes="Conservative citation-backed answer with explicit refusal on low-support retrieval.",
        )
    return TaskRuntimeDescriptor(
        task_id=task.task_id,
        category=task.category,
        enabled=task.enabled,
        output_label=task.output_label,
        execution_path="provider.stub_text",
        provider_mode=settings.provider_mode,
        stubbed=True,
        notes="Foundation-phase deterministic stub path through the provider gateway.",
    )


def _build_category_summary(
    *,
    category: TaskCategory,
    tasks: list[TaskRuntimeDescriptor],
) -> TaskRuntimeCategorySummary:
    category_tasks = [task for task in tasks if task.category == category]
    return TaskRuntimeCategorySummary(
        category=category,
        task_count=len(category_tasks),
        enabled_task_count=sum(1 for task in category_tasks if task.enabled),
        stubbed_task_count=sum(1 for task in category_tasks if task.enabled and task.stubbed),
    )
