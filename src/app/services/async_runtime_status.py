from __future__ import annotations

from app.config import settings
from app.contracts.async_runtime import (
    AsyncQueueMode,
    AsyncRuntimeStatusResponse,
    AsyncWorkerMode,
)
from app.services.async_job_service import build_async_job_catalog
from app.services.async_job_type_catalog import list_async_job_types
from app.services.async_queue_backend_service import list_async_queue_backends
from app.services.async_worker_execution_service import list_async_worker_executions


def build_async_runtime_status() -> AsyncRuntimeStatusResponse:
    job_catalog = build_async_job_catalog()
    queue_backends = list_async_queue_backends()
    worker_executions = list_async_worker_executions()
    return AsyncRuntimeStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        queue_mode=AsyncQueueMode.STUBBED,
        worker_mode=AsyncWorkerMode.DOCUMENTED_ONLY,
        queue_backend="service_database",
        supported_queue_backends=queue_backends,
        active_worker_execution="none",
        supported_worker_executions=worker_executions,
        active_worker_count=0,
        enqueued_job_count=job_catalog.queued_job_count,
        recorded_job_count=job_catalog.job_count,
        supported_job_types=list_async_job_types(),
        message=(
            "Async submission and catalog state are now durable for allowlisted job types, but "
            "dedicated worker execution is not active yet."
        ),
    )
