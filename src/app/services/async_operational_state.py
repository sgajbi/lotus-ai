from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.contracts.async_runtime import AsyncCutoverState, AsyncJobStatus
from app.services.async_delivery_queue import (
    AsyncQueueObservabilitySnapshot,
    get_async_delivery_queue,
)
from app.services.async_runtime_posture import get_async_runtime_posture
from app.services.async_runtime_store import get_async_runtime_store


@dataclass(frozen=True)
class AsyncOperationalState:
    active_worker_ids: list[str]
    queue_snapshot: AsyncQueueObservabilitySnapshot
    drain_mode_active: bool
    degraded_findings: list[str]


def build_async_operational_state() -> AsyncOperationalState:
    posture = get_async_runtime_posture()
    active_worker_ids = sorted(
        {lease.worker_id for lease in get_async_runtime_store().list_leases()}
    )
    queued_jobs = [
        job
        for job in get_async_runtime_store().list_jobs()
        if job.lifecycle_status == AsyncJobStatus.QUEUED.value
    ]
    queue_snapshot = get_async_delivery_queue().snapshot()
    drain_mode_active = settings.async_worker_drain_enabled
    degraded_findings: list[str] = []

    if posture.queue_backend == "redis_queue" and not queue_snapshot.backend_available:
        degraded_findings.append(
            "Managed queue backend is unavailable; queue-backed async delivery cannot currently be treated as healthy."
        )
    if posture.cutover_state == AsyncCutoverState.DEGRADED_FALLBACK:
        degraded_findings.append(
            "Async worker rollout is operating in an explicit degraded fallback posture."
        )
    if posture.cutover_state == AsyncCutoverState.DEDICATED_WORKERS_ACTIVE:
        if drain_mode_active:
            degraded_findings.append(
                "Dedicated workers are in drain mode; new queue deliveries are intentionally not being claimed."
            )
        if queue_snapshot.pending_delivery_count > 0 and not active_worker_ids:
            degraded_findings.append(
                "Queue backlog exists for dedicated-worker execution, but no active worker leases are currently visible."
            )
        if queued_jobs and queue_snapshot.pending_delivery_count == 0 and not active_worker_ids:
            degraded_findings.append(
                "Queued async runtime jobs exist without pending managed-queue deliveries or active worker leases; use REDRIVE_QUEUED_JOB or QUARANTINE_QUEUED_JOB to reconcile queue/database truth."
            )

    return AsyncOperationalState(
        active_worker_ids=active_worker_ids,
        queue_snapshot=queue_snapshot,
        drain_mode_active=drain_mode_active,
        degraded_findings=degraded_findings,
    )
