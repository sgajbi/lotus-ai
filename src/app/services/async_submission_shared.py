from __future__ import annotations

from app.contracts.async_runtime import AsyncCutoverState
from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeJobRecord,
)
from app.services.async_delivery_queue import AsyncQueueDeliveryMessage, get_async_delivery_queue
from app.services.async_runtime_posture import get_async_runtime_posture


def publish_async_attempt_if_configured(
    *,
    job: AsyncRuntimeJobRecord,
    attempt: AsyncRuntimeAttemptRecord,
    delivery_id: str | None = None,
) -> bool:
    posture = get_async_runtime_posture()
    if posture.cutover_state not in {
        AsyncCutoverState.QUEUE_DELIVERY_SHADOW,
        AsyncCutoverState.DEDICATED_WORKERS_ACTIVE,
        AsyncCutoverState.DEGRADED_FALLBACK,
    }:
        return False
    result = get_async_delivery_queue().enqueue(
        message=AsyncQueueDeliveryMessage(
            delivery_id=delivery_id or attempt.attempt_id,
            job_id=job.job_id,
            attempt_id=attempt.attempt_id,
            job_type=job.job_type,
            target_id=job.target_id,
            caller_app=job.caller_app,
            correlation_id=job.correlation_id,
            submitted_at=job.submitted_at,
        )
    )
    return result.published
