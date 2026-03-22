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
            selection_state="ACTIVE_FOUNDATION_DEFAULT",
            supports_durable_queue=False,
            supports_worker_scaling=False,
            notes=(
                "Foundation default. lotus-ai exposes async contracts and artifact history without "
                "activating a live queue backend."
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
        active_queue_backend="none",
        backend_count=len(backends),
        backends=backends,
    )
