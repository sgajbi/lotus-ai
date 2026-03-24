from __future__ import annotations

from app.config import settings
from app.contracts.async_runtime import (
    AsyncWorkerExecutionCatalogResponse,
    AsyncWorkerExecutionDescriptor,
)
from app.services.async_runtime_posture import get_async_runtime_posture


def list_async_worker_executions() -> list[AsyncWorkerExecutionDescriptor]:
    posture = get_async_runtime_posture()
    return [
        AsyncWorkerExecutionDescriptor(
            worker_id="none",
            enabled=False,
            execution_class="NO_WORKER_RUNTIME",
            selection_state="DOCUMENTED_FOUNDATION_BASELINE",
            supports_horizontal_scaling=False,
            supports_job_isolation=False,
            notes=(
                "Historical foundation baseline before durable worker claim and lease semantics "
                "were activated."
            ),
        ),
        AsyncWorkerExecutionDescriptor(
            worker_id="in_process_stub",
            enabled=posture.active_worker_execution == "in_process_stub",
            execution_class="STUBBED_WORKER_RUNTIME",
            selection_state=(
                "ACTIVE_DEFAULT"
                if posture.active_worker_execution == "in_process_stub"
                else "AVAILABLE_FALLBACK"
            ),
            supports_horizontal_scaling=False,
            supports_job_isolation=True,
            notes=(
                "Current durable worker posture for in-process execution. Claim, lease, heartbeat, "
                "recovery, and terminal-state transitions remain authoritative in the service database."
            ),
        ),
        AsyncWorkerExecutionDescriptor(
            worker_id="queue_backed_workers",
            enabled=posture.active_worker_execution == "queue_backed_workers",
            execution_class="DEDICATED_WORKER_FLEET",
            selection_state=(
                "ACTIVE_PRIMARY"
                if posture.active_worker_execution == "queue_backed_workers"
                else "WIRED_FUTURE_CUTOVER"
            ),
            supports_horizontal_scaling=True,
            supports_job_isolation=True,
            notes=(
                "Target bank-grade async execution model using dedicated worker replicas behind a "
                "governed queue backend."
            ),
        ),
    ]


def build_async_worker_execution_catalog() -> AsyncWorkerExecutionCatalogResponse:
    posture = get_async_runtime_posture()
    workers = list_async_worker_executions()
    return AsyncWorkerExecutionCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        active_worker_execution=posture.active_worker_execution,
        worker_count=len(workers),
        workers=workers,
    )
