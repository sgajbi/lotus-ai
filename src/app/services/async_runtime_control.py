from __future__ import annotations

from dataclasses import replace

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.access_control import AuthorizationCapabilityType, AuthorizationDecision
from app.contracts.async_runtime import (
    AsyncControlActionRequest,
    AsyncControlActionResponse,
    AsyncControlActionType,
    AsyncControlHistoryResponse,
    AsyncJobStatus,
)
from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeControlEventRecord,
    AsyncRuntimeJobRecord,
)
from app.services.eval_attempt_runtime import (
    abandon_active_evaluation_attempt,
    queue_next_evaluation_attempt,
)
from app.services.async_job_mapping import map_async_runtime_control_event
from app.services.access_control_authorization import authorize_request, require_authorized
from app.services.async_delivery_recovery import (
    quarantine_queued_async_job,
    redrive_queued_async_job,
)
from app.services.async_runtime_store import get_async_runtime_store
from app.services.async_runtime_transitions import queue_next_async_attempt


def build_async_control_history(*, limit: int = 20) -> AsyncControlHistoryResponse:
    store = get_async_runtime_store()
    return AsyncControlHistoryResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        control_plane_store_mode=settings.async_runtime_store_mode,
        supported_action_types=list(AsyncControlActionType),
        latest_events=[
            map_async_runtime_control_event(event)
            for event in store.list_control_events(limit=max(limit, 1))
        ],
        notes=[
            "Duplicate runtime-backed retrieval-index submissions are rejected while an active queued, claimed, or running job already owns the same caller and target.",
            "Retry, replay, requeue, and manual abandon are explicit async control-plane events rather than implicit table edits.",
            (
                "Async control-plane review is durable across restart when LOTUS_AI_ASYNC_RUNTIME_STORE_MODE=sqlalchemy."
                if settings.async_runtime_store_mode == "sqlalchemy"
                else "Async control-plane review is currently process-local because the in-memory async-runtime store is active."
            ),
        ],
    )


def apply_async_control_action(request: AsyncControlActionRequest) -> AsyncControlActionResponse:
    authorization = require_authorized(
        authorize_request(
            caller_app=request.caller_app,
            capability_type=AuthorizationCapabilityType.ASYNC_CONTROL,
        )
    )
    store = get_async_runtime_store()
    job = store.get_job(job_id=request.job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Async job '{request.job_id}' was not found in runtime state.",
        )

    event = _apply_control_action(job=job, request=request, authorization=authorization)
    store.save_control_event(event)
    descriptor = map_async_runtime_control_event(event)
    return AsyncControlActionResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        event=descriptor,
        summary=[
            f"Applied async control action `{request.action_type.value}` to job `{request.job_id}`.",
            f"Job moved from `{event.prior_status}` to `{event.resulting_status}`.",
            f"Action requested by `{request.requested_by}` and approved by `{request.approved_by}`.",
        ],
    )


def _apply_control_action(
    *,
    job: AsyncRuntimeJobRecord,
    request: AsyncControlActionRequest,
    authorization: AuthorizationDecision,
) -> AsyncRuntimeControlEventRecord:
    action_type = request.action_type
    if action_type == AsyncControlActionType.RETRY_FAILED_JOB:
        created_attempt = _retry_failed_job(job=job, reason=request.reason)
        _sync_evaluation_retryable_action(job=job, reason=request.reason, prefix="Manual retry")
        resulting_status = AsyncJobStatus.QUEUED.value
        affected_attempt_id = created_attempt.attempt_id
    elif action_type == AsyncControlActionType.REPLAY_TERMINAL_JOB:
        created_attempt = _replay_terminal_job(job=job, reason=request.reason)
        _sync_evaluation_retryable_action(job=job, reason=request.reason, prefix="Manual replay")
        resulting_status = AsyncJobStatus.QUEUED.value
        affected_attempt_id = created_attempt.attempt_id
    elif action_type == AsyncControlActionType.REQUEUE_ABANDONED_JOB:
        created_attempt = _requeue_abandoned_job(job=job, reason=request.reason)
        _sync_evaluation_retryable_action(job=job, reason=request.reason, prefix="Manual requeue")
        resulting_status = AsyncJobStatus.QUEUED.value
        affected_attempt_id = created_attempt.attempt_id
    elif action_type == AsyncControlActionType.ABANDON_ACTIVE_JOB:
        affected_attempt_id = _abandon_active_job(job=job, reason=request.reason)
        _sync_evaluation_abandon(job=job, reason=request.reason)
        resulting_status = AsyncJobStatus.ABANDONED.value
    elif action_type == AsyncControlActionType.REDRIVE_QUEUED_JOB:
        event = redrive_queued_async_job(
            job=job,
            requested_by=request.requested_by,
            approved_by=request.approved_by,
            reason=request.reason,
            authorization=authorization,
        )
        return event
    elif action_type == AsyncControlActionType.QUARANTINE_QUEUED_JOB:
        event = quarantine_queued_async_job(
            job=job,
            requested_by=request.requested_by,
            approved_by=request.approved_by,
            reason=request.reason,
            authorization=authorization,
        )
        return event
    else:
        raise RuntimeError("Unsupported async control action.")

    return AsyncRuntimeControlEventRecord(
        event_id=f"async_ctrl_evt_{uuid4().hex[:12]}",
        job_id=job.job_id,
        action_type=action_type.value,
        requested_by=request.requested_by,
        approved_by=request.approved_by,
        reason=request.reason,
        prior_status=job.lifecycle_status,
        resulting_status=resulting_status,
        affected_attempt_id=affected_attempt_id,
        authorization=authorization,
        recorded_at=_utcnow(),
    )


def _retry_failed_job(*, job: AsyncRuntimeJobRecord, reason: str) -> AsyncRuntimeAttemptRecord:
    if job.lifecycle_status != AsyncJobStatus.FAILED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Async job '{job.job_id}' is not in FAILED state and cannot be retried.",
        )
    return queue_next_async_attempt(
        store=get_async_runtime_store(),
        job=job,
        reason_message=f"Manual retry queued after operator action: {reason}",
    )


def _replay_terminal_job(*, job: AsyncRuntimeJobRecord, reason: str) -> AsyncRuntimeAttemptRecord:
    if job.lifecycle_status not in {
        AsyncJobStatus.COMPLETED.value,
        AsyncJobStatus.FAILED.value,
        AsyncJobStatus.ABANDONED.value,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Async job '{job.job_id}' is not terminal and cannot be replayed.",
        )
    return queue_next_async_attempt(
        store=get_async_runtime_store(),
        job=job,
        reason_message=f"Manual replay queued after operator action: {reason}",
    )


def _requeue_abandoned_job(*, job: AsyncRuntimeJobRecord, reason: str) -> AsyncRuntimeAttemptRecord:
    if job.lifecycle_status != AsyncJobStatus.ABANDONED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Async job '{job.job_id}' is not in ABANDONED state and cannot be requeued.",
        )
    return queue_next_async_attempt(
        store=get_async_runtime_store(),
        job=job,
        reason_message=f"Manual requeue queued after operator action: {reason}",
    )


def _abandon_active_job(*, job: AsyncRuntimeJobRecord, reason: str) -> str:
    if job.lifecycle_status not in {
        AsyncJobStatus.CLAIMED.value,
        AsyncJobStatus.RUNNING.value,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Async job '{job.job_id}' is not actively claimed or running and cannot be abandoned.",
        )
    store = get_async_runtime_store()
    lease = store.get_active_lease(job_id=job.job_id)
    if lease is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Async job '{job.job_id}' has no active lease to abandon.",
        )
    attempt = store.get_attempt(attempt_id=lease.attempt_id)
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Active runtime attempt '{lease.attempt_id}' was not found for job '{job.job_id}'.",
        )
    now = _utcnow()
    store.save_attempt(
        AsyncRuntimeAttemptRecord(
            attempt_id=attempt.attempt_id,
            job_id=attempt.job_id,
            attempt_number=attempt.attempt_number,
            lifecycle_status=AsyncJobStatus.ABANDONED.value,
            worker_id=attempt.worker_id,
            claimed_at=attempt.claimed_at,
            heartbeat_at=attempt.heartbeat_at,
            started_at=attempt.started_at,
            completed_at=now,
            failure_reason="MANUAL_ABANDON",
            recorded_message=f"Attempt manually abandoned: {reason}",
        )
    )
    store.delete_lease(lease_id=lease.lease_id)
    store.save_job(
        replace(
            job,
            lifecycle_status=AsyncJobStatus.ABANDONED.value,
            latest_message=f"Job manually abandoned: {reason}",
        )
    )
    return attempt.attempt_id


def _utcnow() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sync_evaluation_retryable_action(
    *,
    job: AsyncRuntimeJobRecord,
    reason: str,
    prefix: str,
) -> None:
    if job.related_evaluation_run_id is None:
        return
    queue_next_evaluation_attempt(
        run_id=job.related_evaluation_run_id,
        reason_message=f"{prefix} queued after operator action: {reason}",
    )


def _sync_evaluation_abandon(*, job: AsyncRuntimeJobRecord, reason: str) -> None:
    if job.related_evaluation_run_id is None:
        return
    abandon_active_evaluation_attempt(
        run_id=job.related_evaluation_run_id,
        reason_message=f"Evaluation attempt manually abandoned: {reason}",
        failure_reason="MANUAL_ABANDON",
    )
