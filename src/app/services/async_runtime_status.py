from __future__ import annotations

from app.config import settings
from app.contracts.async_runtime import (
    AsyncJobTypeDescriptor,
    AsyncQueueMode,
    AsyncRuntimeStatusResponse,
    AsyncWorkerMode,
)
from app.services.async_job_service import build_async_job_catalog
from app.services.async_queue_backend_service import list_async_queue_backends
from app.services.async_worker_execution_service import list_async_worker_executions


def build_async_runtime_status() -> AsyncRuntimeStatusResponse:
    job_catalog = build_async_job_catalog()
    queue_backends = list_async_queue_backends()
    worker_executions = list_async_worker_executions()
    queue_mode = AsyncQueueMode(settings.async_queue_mode.upper())
    worker_mode = AsyncWorkerMode(settings.async_worker_mode.upper())
    stubbed_runtime = (
        queue_mode == AsyncQueueMode.STUBBED and worker_mode == AsyncWorkerMode.STUBBED
    )
    return AsyncRuntimeStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        queue_mode=queue_mode,
        worker_mode=worker_mode,
        queue_backend="none",
        supported_queue_backends=queue_backends,
        active_worker_execution="in_process_stub" if stubbed_runtime else "none",
        supported_worker_executions=worker_executions,
        active_worker_count=1 if stubbed_runtime else 0,
        enqueued_job_count=job_catalog.queued_job_count,
        recorded_job_count=job_catalog.job_count,
        supported_job_types=[
            AsyncJobTypeDescriptor(
                job_type="retrieval_indexing",
                enabled=stubbed_runtime,
                execution_path="in_process_stub" if stubbed_runtime else "future_worker_queue",
                notes=(
                    "Retrieval indexing runs through the in-process stub path when async stub "
                    "runtime is enabled; the long-term target remains worker-backed execution."
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
            "Async runtime contracts are defined. Queue-backed execution remains disabled in the "
            "foundation phase, but retrieval indexing can run through an in-process stub path "
            "when explicitly enabled for controlled validation."
        ),
    )
