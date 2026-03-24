from __future__ import annotations

from app.contracts.async_runtime import AsyncJobTypeDescriptor


def list_async_job_types() -> list[AsyncJobTypeDescriptor]:
    return [
        AsyncJobTypeDescriptor(
            job_type="retrieval_indexing",
            enabled=True,
            execution_path="durable_runtime_worker_execution",
            notes=(
                "Retrieval indexing now runs through durable async submission, claim, lease, and "
                "completion semantics for explicit retrieval index job targets."
            ),
        ),
        AsyncJobTypeDescriptor(
            job_type="evaluation_execution",
            enabled=True,
            execution_path="durable_runtime_worker_execution",
            notes=(
                "Evaluation execution now supports narrow runtime-backed submission, worker claim, "
                "case execution, and persisted verdict history for allowlisted fixture families."
            ),
        ),
        AsyncJobTypeDescriptor(
            job_type="document_ingestion",
            enabled=True,
            execution_path="durable_runtime_worker_execution",
            notes=(
                "Bounded document ingestion now runs through durable async submission, claim, "
                "replay, and completion semantics for governed retrieval ingestion job targets."
            ),
        ),
    ]


def get_async_job_type_descriptor(*, job_type: str) -> AsyncJobTypeDescriptor | None:
    return next(
        (descriptor for descriptor in list_async_job_types() if descriptor.job_type == job_type),
        None,
    )
