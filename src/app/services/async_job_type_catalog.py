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
            enabled=False,
            execution_path="future_worker_queue",
            notes=(
                "Evaluation execution remains staged and artifact-backed until a later async "
                "execution slice activates runtime-backed evaluation jobs."
            ),
        ),
        AsyncJobTypeDescriptor(
            job_type="document_ingestion",
            enabled=False,
            execution_path="future_worker_queue",
            notes=(
                "Large document ingestion remains a documented future async path rather than an "
                "active runtime-backed workflow."
            ),
        ),
    ]


def get_async_job_type_descriptor(*, job_type: str) -> AsyncJobTypeDescriptor | None:
    return next(
        (descriptor for descriptor in list_async_job_types() if descriptor.job_type == job_type),
        None,
    )
