from __future__ import annotations

from app.config import settings
from app.contracts.async_runtime import AsyncRuntimeStatusResponse
from app.services.async_job_service import build_async_job_catalog
from app.services.async_job_type_catalog import list_async_job_types
from app.services.async_operational_state import build_async_operational_state
from app.services.async_queue_backend_service import list_async_queue_backends
from app.services.async_runtime_posture import get_async_runtime_posture
from app.services.async_worker_execution_service import list_async_worker_executions


def build_async_runtime_status() -> AsyncRuntimeStatusResponse:
    job_catalog = build_async_job_catalog()
    queue_backends = list_async_queue_backends()
    worker_executions = list_async_worker_executions()
    posture = get_async_runtime_posture()
    operational_state = build_async_operational_state()
    return AsyncRuntimeStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        cutover_state=posture.cutover_state,
        queue_mode=posture.queue_mode,
        worker_mode=posture.worker_mode,
        queue_backend=posture.queue_backend,
        supported_queue_backends=queue_backends,
        active_worker_execution=posture.active_worker_execution,
        supported_worker_executions=worker_executions,
        active_worker_count=len(operational_state.active_worker_ids),
        active_worker_ids=operational_state.active_worker_ids,
        enqueued_job_count=job_catalog.queued_job_count,
        recorded_job_count=job_catalog.job_count,
        queue_backlog_count=operational_state.queue_snapshot.pending_delivery_count,
        duplicate_delivery_count=operational_state.queue_snapshot.duplicate_delivery_count,
        redelivery_count=operational_state.queue_snapshot.redelivery_count,
        drain_mode_active=operational_state.drain_mode_active,
        degraded_findings=operational_state.degraded_findings,
        supported_job_types=list_async_job_types(),
        message=(
            "Async job truth remains durable in the service database for the allowlisted job types. "
            "The current cutover state exposes whether managed queue delivery is disabled, running in "
            "shadow mode, serving a dedicated worker fleet, or operating in an explicit degraded fallback."
        ),
    )
