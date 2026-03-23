from __future__ import annotations

from app.config import settings
from app.contracts.async_runtime import (
    AsyncQueueBackendCatalogResponse,
    AsyncQueueBackendDescriptor,
)


def list_async_queue_backends() -> list[AsyncQueueBackendDescriptor]:
    return [
        AsyncQueueBackendDescriptor(
            backend_id="none",
            enabled=False,
            backend_class="NO_QUEUE",
            selection_state="DOCUMENTED_FOUNDATION_BASELINE",
            supports_durable_queue=False,
            supports_worker_scaling=False,
            notes=(
                "Former foundation default before durable runtime-backed async submission was "
                "introduced."
            ),
        ),
        AsyncQueueBackendDescriptor(
            backend_id="service_database",
            enabled=True,
            backend_class="SERVICE_DATABASE_QUEUE",
            selection_state="ACTIVE_SLICE_2_DEFAULT",
            supports_durable_queue=True,
            supports_worker_scaling=False,
            notes=(
                "Current Slice 2 default. Async job submission persists to the service database, "
                "but dedicated worker claim and scaling are not active yet."
            ),
        ),
        AsyncQueueBackendDescriptor(
            backend_id="redis_queue",
            enabled=False,
            backend_class="MANAGED_QUEUE",
            selection_state="DOCUMENTED_FUTURE_OPTION",
            supports_durable_queue=True,
            supports_worker_scaling=True,
            notes=(
                "Candidate future queue backend for worker-backed async execution once live async "
                "processing is enabled."
            ),
        ),
        AsyncQueueBackendDescriptor(
            backend_id="kafka_orchestrated",
            enabled=False,
            backend_class="EVENT_STREAM_BRIDGE",
            selection_state="DOCUMENTED_FUTURE_OPTION",
            supports_durable_queue=True,
            supports_worker_scaling=True,
            notes=(
                "Documented future option for event-driven orchestration where lotus-ai async work "
                "must integrate with broader platform event flows."
            ),
        ),
    ]


def build_async_queue_backend_catalog() -> AsyncQueueBackendCatalogResponse:
    backends = list_async_queue_backends()
    return AsyncQueueBackendCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        active_queue_backend="service_database",
        backend_count=len(backends),
        backends=backends,
    )
