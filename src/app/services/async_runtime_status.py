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
from app.services.async_runtime_store import get_async_runtime_store
from app.services.async_worker_execution_service import list_async_worker_executions


def build_async_runtime_status() -> AsyncRuntimeStatusResponse:
    job_catalog = build_async_job_catalog()
    queue_backends = list_async_queue_backends()
    worker_executions = list_async_worker_executions()
    active_lease_workers = {lease.worker_id for lease in get_async_runtime_store().list_leases()}
    return AsyncRuntimeStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        queue_mode=AsyncQueueMode.STUBBED,
        worker_mode=AsyncWorkerMode.STUBBED,
        queue_backend="service_database",
        supported_queue_backends=queue_backends,
        active_worker_execution="in_process_stub",
        supported_worker_executions=worker_executions,
        active_worker_count=len(active_lease_workers),
        enqueued_job_count=job_catalog.queued_job_count,
        recorded_job_count=job_catalog.job_count,
        supported_job_types=list_async_job_types(),
        message=(
            "Async submission, claim, lease, recovery, and terminal-state tracking are durable "
            "for a narrow allowlist, with retrieval indexing and evaluation execution already running "
            "through the runtime-backed in-process worker path. Dedicated queue-backed worker fleet "
            "execution is still disabled."
        ),
    )
