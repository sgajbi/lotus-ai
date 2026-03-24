from __future__ import annotations

from app.config import settings
from app.contracts.async_runtime import (
    AsyncQueueBackendCatalogResponse,
    AsyncQueueBackendDescriptor,
)
from app.services.async_runtime_posture import get_async_runtime_posture


def list_async_queue_backends() -> list[AsyncQueueBackendDescriptor]:
    posture = get_async_runtime_posture()
    return [
        AsyncQueueBackendDescriptor(
            backend_id="none",
            enabled=posture.queue_backend == "none",
            backend_class="NO_QUEUE",
            selection_state=(
                "ACTIVE_DEFAULT" if posture.queue_backend == "none" else "AVAILABLE_FALLBACK"
            ),
            supports_durable_queue=False,
            supports_worker_scaling=False,
            notes=(
                "No managed queue delivery is active. The service database remains the authoritative "
                "async state store, and API-triggered work stays on the durable in-process worker path."
            ),
        ),
        AsyncQueueBackendDescriptor(
            backend_id="redis_queue",
            enabled=posture.queue_backend == "redis_queue",
            backend_class="MANAGED_QUEUE",
            selection_state=(
                "ACTIVE_SHADOW_OR_PRIMARY"
                if posture.queue_backend == "redis_queue"
                else "WIRED_FUTURE_CUTOVER"
            ),
            supports_durable_queue=True,
            supports_worker_scaling=True,
            notes=(
                "Managed queue delivery path for dedicated-worker rollout. Queue messages carry "
                "durable job references only; the service database remains authoritative async truth."
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
    posture = get_async_runtime_posture()
    backends = list_async_queue_backends()
    return AsyncQueueBackendCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        active_queue_backend=posture.queue_backend,
        backend_count=len(backends),
        backends=backends,
    )
