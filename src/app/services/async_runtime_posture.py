from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.contracts.async_runtime import AsyncCutoverState, AsyncQueueMode, AsyncWorkerMode


@dataclass(frozen=True)
class AsyncRuntimePosture:
    cutover_state: AsyncCutoverState
    queue_mode: AsyncQueueMode
    worker_mode: AsyncWorkerMode
    queue_backend: str
    active_worker_execution: str


def get_async_runtime_posture() -> AsyncRuntimePosture:
    cutover_state = AsyncCutoverState(settings.async_cutover_state)
    queue_backend_mode = settings.async_queue_backend_mode

    if cutover_state == AsyncCutoverState.IN_PROCESS_ONLY:
        return AsyncRuntimePosture(
            cutover_state=cutover_state,
            queue_mode=AsyncQueueMode.DISABLED,
            worker_mode=AsyncWorkerMode.IN_PROCESS_ONLY,
            queue_backend="none",
            active_worker_execution="in_process_stub",
        )
    if cutover_state == AsyncCutoverState.QUEUE_DELIVERY_SHADOW:
        _require_redis_backend(queue_backend_mode=queue_backend_mode)
        return AsyncRuntimePosture(
            cutover_state=cutover_state,
            queue_mode=AsyncQueueMode.SHADOW,
            worker_mode=AsyncWorkerMode.IN_PROCESS_ONLY,
            queue_backend="redis_queue",
            active_worker_execution="in_process_stub",
        )
    if cutover_state == AsyncCutoverState.DEDICATED_WORKERS_ACTIVE:
        _require_redis_backend(queue_backend_mode=queue_backend_mode)
        return AsyncRuntimePosture(
            cutover_state=cutover_state,
            queue_mode=AsyncQueueMode.ACTIVE,
            worker_mode=AsyncWorkerMode.DEDICATED,
            queue_backend="redis_queue",
            active_worker_execution="queue_backed_workers",
        )
    _require_redis_backend(queue_backend_mode=queue_backend_mode)
    return AsyncRuntimePosture(
        cutover_state=cutover_state,
        queue_mode=AsyncQueueMode.ACTIVE,
        worker_mode=AsyncWorkerMode.DEGRADED_FALLBACK,
        queue_backend="redis_queue",
        active_worker_execution="degraded_fallback",
    )


def _require_redis_backend(*, queue_backend_mode: str) -> None:
    if queue_backend_mode != "redis":
        raise RuntimeError(
            "LOTUS_AI_ASYNC_QUEUE_BACKEND_MODE=redis is required for queue-backed async cutover states."
        )
