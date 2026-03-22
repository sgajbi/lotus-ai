from __future__ import annotations

from app.config import settings
from app.contracts.async_runtime import (
    AsyncWorkerExecutionCatalogResponse,
    AsyncWorkerExecutionDescriptor,
)


def list_async_worker_executions() -> list[AsyncWorkerExecutionDescriptor]:
    return [
        AsyncWorkerExecutionDescriptor(
            worker_id="none",
            enabled=False,
            execution_class="NO_WORKER_RUNTIME",
            selection_state="ACTIVE_FOUNDATION_DEFAULT",
            supports_horizontal_scaling=False,
            supports_job_isolation=False,
            notes=(
                "Foundation default. lotus-ai exposes async contracts and artifacts without "
                "running dedicated background workers."
            ),
        ),
        AsyncWorkerExecutionDescriptor(
            worker_id="in_process_stub",
            enabled=False,
            execution_class="STUBBED_WORKER_RUNTIME",
            selection_state="DOCUMENTED_FUTURE_OPTION",
            supports_horizontal_scaling=False,
            supports_job_isolation=True,
            notes=(
                "Documented future option for tightly controlled non-production validation where "
                "worker semantics are exercised without deploying a full queue-backed fleet."
            ),
        ),
        AsyncWorkerExecutionDescriptor(
            worker_id="queue_backed_workers",
            enabled=False,
            execution_class="DEDICATED_WORKER_FLEET",
            selection_state="DOCUMENTED_FUTURE_OPTION",
            supports_horizontal_scaling=True,
            supports_job_isolation=True,
            notes=(
                "Target bank-grade async execution model using dedicated worker replicas behind a "
                "governed queue backend."
            ),
        ),
    ]


def build_async_worker_execution_catalog() -> AsyncWorkerExecutionCatalogResponse:
    workers = list_async_worker_executions()
    return AsyncWorkerExecutionCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        active_worker_execution="none",
        worker_count=len(workers),
        workers=workers,
    )
