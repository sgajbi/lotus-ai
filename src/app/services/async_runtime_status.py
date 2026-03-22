from __future__ import annotations

from app.config import settings
from app.contracts.async_runtime import (
    AsyncJobTypeDescriptor,
    AsyncQueueMode,
    AsyncRuntimeStatusResponse,
    AsyncWorkerMode,
)


def build_async_runtime_status() -> AsyncRuntimeStatusResponse:
    return AsyncRuntimeStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        queue_mode=AsyncQueueMode.DISABLED,
        worker_mode=AsyncWorkerMode.DOCUMENTED_ONLY,
        queue_backend="none",
        active_worker_count=0,
        enqueued_job_count=0,
        supported_job_types=[
            AsyncJobTypeDescriptor(
                job_type="retrieval_indexing",
                enabled=False,
                execution_path="future_worker_queue",
                notes=(
                    "Retrieval indexing is expected to move to worker-backed execution once live "
                    "embedding and vector indexing are activated."
                ),
            ),
            AsyncJobTypeDescriptor(
                job_type="evaluation_execution",
                enabled=False,
                execution_path="future_worker_queue",
                notes=(
                    "Evaluation execution remains artifact-only in foundation phase and has not "
                    "yet been activated as a live worker flow."
                ),
            ),
            AsyncJobTypeDescriptor(
                job_type="document_ingestion",
                enabled=False,
                execution_path="future_worker_queue",
                notes=(
                    "Large document ingestion is planned as an async worker path rather than a "
                    "synchronous API responsibility."
                ),
            ),
        ],
        message=(
            "Async runtime contracts are defined, but queue-backed execution remains disabled in "
            "the foundation phase."
        ),
    )
