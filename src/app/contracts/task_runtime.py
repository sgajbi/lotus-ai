from __future__ import annotations

from pydantic import BaseModel, Field

from app.contracts.tasks import OutputLabel, TaskCategory


class TaskRuntimeDescriptor(BaseModel):
    task_id: str = Field(description="Stable Lotus AI task identifier.")
    category: TaskCategory = Field(description="Task category exposed by lotus-ai.")
    enabled: bool = Field(description="Whether the task is currently enabled for execution.")
    output_label: OutputLabel = Field(description="Output label emitted by the task.")
    execution_path: str = Field(description="Current internal execution path used for the task.")
    provider_mode: str = Field(description="Provider mode associated with the task execution path.")
    stubbed: bool = Field(description="Whether the current task path is stub-backed.")
    notes: str = Field(description="Human-readable explanation of the current task runtime posture.")


class TaskRuntimeCategorySummary(BaseModel):
    category: TaskCategory = Field(description="Task category represented by the summary row.")
    task_count: int = Field(description="Total number of tasks in the category.")
    enabled_task_count: int = Field(description="Number of enabled tasks in the category.")
    stubbed_task_count: int = Field(description="Number of stub-backed tasks in the category.")


class TaskRuntimeStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the task runtime status.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    enabled_task_count: int = Field(description="Number of currently enabled bounded tasks.")
    stubbed_task_count: int = Field(description="Number of enabled tasks that are still stub-backed.")
    retrieval_backed_task_count: int = Field(
        description="Number of enabled tasks currently backed by the governed retrieval path."
    )
    categories: list[TaskRuntimeCategorySummary] = Field(
        description="Category-level runtime summary across bounded lotus-ai tasks."
    )
    tasks: list[TaskRuntimeDescriptor] = Field(
        description="Per-task runtime posture for bounded lotus-ai tasks."
    )
