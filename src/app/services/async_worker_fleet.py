from __future__ import annotations

import logging
from dataclasses import dataclass
from time import sleep

from app.config import settings
from app.services.async_worker_health import record_worker_liveness
from app.contracts.async_runtime import AsyncCutoverState
from app.services.async_delivery_queue import AsyncQueueDeliveryMessage, get_async_delivery_queue
from app.services.async_delivery_recovery import recover_unhandled_delivery
from app.services.async_runtime_posture import get_async_runtime_posture
from app.services.eval_async_execution import run_evaluation_execution_job_by_id
from app.services.retrieval_ingestion_async_execution import run_retrieval_ingestion_job_by_id
from app.services.retrieval_async_execution import run_retrieval_index_job_by_id
from app.services.workflow_pack_async_execution import run_workflow_pack_execution_job_by_id


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
    if settings.async_worker_drain_enabled:
        return None
    try:
        delivery = get_async_delivery_queue().dequeue(timeout_seconds=timeout_seconds)
    except Exception:
        # A queue backend outage must not kill the worker (issue #369). Before
        # this, a stopped Redis raised ConnectionError straight out of dequeue,
        # the loop had no handler, and the container exited 1 - so the worker
        # could not report an unavailable queue backend, because it was gone
        # before it could record anything. A health contract cannot detect what
        # kills it first.
        #
        # Scoped to the dequeue call alone on purpose: job execution below must
        # keep surfacing its own failures through the existing recovery path,
        # not be swallowed here. The cycle returns as idle, the loop records
        # queue_backend_available=False from the queue's own snapshot, and the
        # health command reports WORKER_QUEUE_BACKEND_UNAVAILABLE until the
        # backend returns. Logged with a traceback so a real dequeue bug is
        # visible rather than silently retried forever.
        logging.getLogger(__name__).warning(
            "async_worker_queue_dequeue_failed",
            extra={"worker_id": worker_id},
            exc_info=True,
        )
        return None
    if delivery is None:
        return None
    result = _dispatch_delivery(worker_id=worker_id, delivery=delivery)
    if not result.handled:
        recover_unhandled_delivery(
            delivery_job_id=delivery.job_id,
            delivery_attempt_id=delivery.attempt_id,
            delivery_job_type=delivery.job_type,
            delivery_target_id=delivery.target_id,
            delivery_caller_app=delivery.caller_app,
            delivery_correlation_id=delivery.correlation_id,
            delivery_submitted_at=delivery.submitted_at,
            worker_id=worker_id,
            reason=(
                "Dedicated worker delivery was dequeued but no durable claim or execution "
                f"was completed for delivery `{delivery.delivery_id}`."
            ),
        )
    return result


def run_dedicated_worker_loop(
    *,
    worker_id: str,
    timeout_seconds: int = 5,
    idle_sleep_seconds: float = 0.25,
    max_cycles: int | None = None,
) -> None:
    completed_cycles = 0
    consecutive_queue_failures = 0
    while max_cycles is None or completed_cycles < max_cycles:
        processed = process_next_async_delivery(
            worker_id=worker_id,
            timeout_seconds=timeout_seconds,
        )
        completed_cycles += 1
        # Recorded every cycle, after the work, so the marker is evidence that
        # this loop ran rather than that the process started (issue #369). An
        # idle worker records too: the container health contract must not
        # require job traffic to report a healthy worker, or a correctly idle
        # worker would look stopped.
        queue_available = _record_worker_liveness_for_cycle(worker_id=worker_id)
        if queue_available:
            consecutive_queue_failures = 0
        else:
            consecutive_queue_failures += 1
        if processed is None:
            sleep(
                _idle_sleep_for_cycle(
                    idle_sleep_seconds=idle_sleep_seconds,
                    consecutive_queue_failures=consecutive_queue_failures,
                )
            )


def _idle_sleep_for_cycle(
    *,
    idle_sleep_seconds: float,
    consecutive_queue_failures: int,
) -> float:
    """Back off while the queue backend is unreachable.

    Surviving a queue outage (issue #369) means the loop keeps running against a
    dead backend. At the normal idle interval that is several failed connections
    per second, each logging a traceback, for as long as the outage lasts -
    unbounded log growth introduced by the fix rather than by the defect.

    Backoff is capped so recovery stays prompt: the worker must return to
    healthy soon after the backend does, and the cap keeps the retry interval
    well inside the health staleness bound so a recovering worker refreshes its
    marker before it can be called stale.
    """

    if consecutive_queue_failures <= 0:
        return idle_sleep_seconds
    shift = min(consecutive_queue_failures, _QUEUE_BACKOFF_SHIFT_CAP)
    backoff = float(idle_sleep_seconds) * float(2**shift)
    return min(backoff, _QUEUE_BACKOFF_MAX_SECONDS)


_QUEUE_BACKOFF_SHIFT_CAP = 8
_QUEUE_BACKOFF_MAX_SECONDS = 5.0


def _record_worker_liveness_for_cycle(*, worker_id: str) -> bool:
    """Record this cycle's worker-owned health evidence.

    The queue snapshot is the existing durable signal for backend reachability
    and already returns backend_available=False rather than raising, so a
    Redis outage becomes recorded evidence instead of an exception that would
    stop the loop writing markers at all.

    A failure to WRITE the marker is logged and swallowed here on purpose: it
    must not kill a worker that is otherwise executing jobs. It is still
    fail-closed, because the unrefreshed marker ages past the staleness bound
    and the health command reports unhealthy. Silence here buys time, never a
    healthy verdict.

    Returns whether the QUEUE BACKEND was reachable, which the loop uses to
    pace its retries.

    That is deliberately not "did this function succeed". An earlier version
    returned False on any failure here, so a marker write that could not reach
    its path made an idle worker with a perfectly healthy queue back off - two
    unrelated faults collapsed into one signal, and a disk problem would have
    silently slowed polling. A failed marker write says nothing about the
    backend, so only queue evidence decides the pacing.
    """

    queue_available = True
    try:
        snapshot = get_async_delivery_queue().snapshot()
        queue_available = bool(snapshot.backend_available)
    except Exception:
        # Failing to obtain the snapshot IS queue evidence: the worker could
        # not ask the backend anything.
        logging.getLogger(__name__).warning(
            "async_worker_queue_snapshot_failed",
            extra={"worker_id": worker_id},
            exc_info=True,
        )
        return False

    try:
        posture = get_async_runtime_posture()
        record_worker_liveness(
            worker_id=worker_id,
            queue_backend_available=queue_available,
            queue_backend_id=snapshot.backend_id,
            cutover_state=posture.cutover_state.value,
            drain_enabled=settings.async_worker_drain_enabled,
        )
    except Exception:
        # Logged and swallowed: it must not kill a worker that is otherwise
        # executing jobs, and it is still fail-closed because the unrefreshed
        # marker ages past the staleness bound and health reports unhealthy.
        logging.getLogger(__name__).warning(
            "async_worker_liveness_record_failed",
            extra={"worker_id": worker_id},
            exc_info=True,
        )
    return queue_available


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
    if delivery.job_type == "document_ingestion":
        ingestion_result = run_retrieval_ingestion_job_by_id(
            async_job_id=delivery.job_id,
            worker_id=worker_id,
        )
        return DedicatedWorkerCycleResult(
            delivery_id=delivery.delivery_id,
            job_id=delivery.job_id,
            job_type=delivery.job_type,
            handled=ingestion_result is not None,
            terminal_status=(
                None if ingestion_result is None else ingestion_result.terminal_status
            ),
        )
    if delivery.job_type == "workflow_pack_execution":
        workflow_pack_result = run_workflow_pack_execution_job_by_id(
            async_job_id=delivery.job_id,
            worker_id=worker_id,
        )
        return DedicatedWorkerCycleResult(
            delivery_id=delivery.delivery_id,
            job_id=delivery.job_id,
            job_type=delivery.job_type,
            handled=workflow_pack_result is not None,
            terminal_status=(
                None if workflow_pack_result is None else workflow_pack_result.terminal_status
            ),
        )
    return DedicatedWorkerCycleResult(
        delivery_id=delivery.delivery_id,
        job_id=delivery.job_id,
        job_type=delivery.job_type,
        handled=False,
        terminal_status=None,
    )
