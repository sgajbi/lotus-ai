from __future__ import annotations

from app.config import settings
from app.contracts.task_runtime import (
    TaskRuntimeCategorySummary,
    TaskRuntimeDescriptor,
    TaskRuntimeStatusResponse,
)
from app.contracts.tasks import CapabilityDescriptor, TaskCategory
from app.services.capability_catalog import build_capability_catalog
from app.services.task_execution_path import build_task_execution_path


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
    execution_path = build_task_execution_path(task)
    return TaskRuntimeDescriptor(
        task_id=task.task_id,
        category=task.category,
        enabled=task.enabled,
        output_label=task.output_label,
        execution_path=execution_path.execution_path,
        provider_mode=execution_path.provider_mode,
        stubbed=execution_path.stubbed,
        notes=execution_path.notes,
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
