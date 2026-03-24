from __future__ import annotations

from dataclasses import dataclass
from time import sleep

from app.contracts.async_runtime import AsyncCutoverState
from app.services.async_delivery_queue import AsyncQueueDeliveryMessage, get_async_delivery_queue
from app.services.async_runtime_posture import get_async_runtime_posture
from app.services.eval_async_execution import run_evaluation_execution_job_by_id
from app.services.retrieval_async_execution import run_retrieval_index_job_by_id


@dataclass(frozen=True)
class DedicatedWorkerCycleResult:
    delivery_id: str
    job_id: str
    job_type: str
    handled: bool
    terminal_status: str | None


def process_next_async_delivery(
    *,
    worker_id: str,
    timeout_seconds: int = 1,
) -> DedicatedWorkerCycleResult | None:
    posture = get_async_runtime_posture()
    if posture.cutover_state != AsyncCutoverState.DEDICATED_WORKERS_ACTIVE:
        return None
    delivery = get_async_delivery_queue().dequeue(timeout_seconds=timeout_seconds)
    if delivery is None:
        return None
    return _dispatch_delivery(worker_id=worker_id, delivery=delivery)


def run_dedicated_worker_loop(
    *,
    worker_id: str,
    timeout_seconds: int = 5,
    idle_sleep_seconds: float = 0.25,
    max_cycles: int | None = None,
) -> None:
    completed_cycles = 0
    while max_cycles is None or completed_cycles < max_cycles:
        processed = process_next_async_delivery(
            worker_id=worker_id,
            timeout_seconds=timeout_seconds,
        )
        completed_cycles += 1
        if processed is None:
            sleep(idle_sleep_seconds)


def _dispatch_delivery(
    *,
    worker_id: str,
    delivery: AsyncQueueDeliveryMessage,
) -> DedicatedWorkerCycleResult:
    if delivery.job_type == "retrieval_indexing":
        retrieval_result = run_retrieval_index_job_by_id(
            async_job_id=delivery.job_id,
            worker_id=worker_id,
        )
        return DedicatedWorkerCycleResult(
            delivery_id=delivery.delivery_id,
            job_id=delivery.job_id,
            job_type=delivery.job_type,
            handled=retrieval_result is not None,
            terminal_status=(
                None if retrieval_result is None else retrieval_result.terminal_status
            ),
        )
    if delivery.job_type == "evaluation_execution":
        evaluation_result = run_evaluation_execution_job_by_id(
            async_job_id=delivery.job_id,
            worker_id=worker_id,
        )
        return DedicatedWorkerCycleResult(
            delivery_id=delivery.delivery_id,
            job_id=delivery.job_id,
            job_type=delivery.job_type,
            handled=evaluation_result is not None,
            terminal_status=None if evaluation_result is None else "COMPLETED",
        )
    return DedicatedWorkerCycleResult(
        delivery_id=delivery.delivery_id,
        job_id=delivery.job_id,
        job_type=delivery.job_type,
        handled=False,
        terminal_status=None,
    )
