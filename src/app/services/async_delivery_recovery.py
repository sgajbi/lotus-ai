from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status

from app.contracts.access_control import AuthorizationDecision
from app.contracts.async_runtime import AsyncControlActionType, AsyncJobStatus
from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeControlEventRecord,
    AsyncRuntimeJobRecord,
)
from app.services.async_runtime_store import get_async_runtime_store
from app.services.async_submission_shared import publish_async_attempt_if_configured


def redrive_queued_async_job(
    *,
    job: AsyncRuntimeJobRecord,
    requested_by: str,
    approved_by: str,
    reason: str,
    authorization: AuthorizationDecision,
) -> AsyncRuntimeControlEventRecord:
    _require_queued_without_lease(job=job, action="redriven")
    attempt = _latest_attempt(job=job)
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Async job '{job.job_id}' has no attempt to re-drive.",
        )
    if attempt.lifecycle_status != AsyncJobStatus.QUEUED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Async job '{job.job_id}' latest attempt is not QUEUED and cannot be re-driven."
            ),
        )
    redrive_delivery_id = f"{attempt.attempt_id}_redrive_{uuid4().hex[:12]}"
    if not publish_async_attempt_if_configured(
        job=job,
        attempt=attempt,
        delivery_id=redrive_delivery_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Async job '{job.job_id}' could not be re-driven because managed queue "
                "publication is inactive."
            ),
        )
    store = get_async_runtime_store()
    message = f"Queued async job re-driven to managed queue: {reason}"
    store.save_job(
        AsyncRuntimeJobRecord(
            job_id=job.job_id,
            job_type=job.job_type,
            target_id=job.target_id,
            lifecycle_status=AsyncJobStatus.QUEUED.value,
            submitted_at=job.submitted_at,
            caller_app=job.caller_app,
            correlation_id=job.correlation_id,
            payload_summary=job.payload_summary,
            execution_path=job.execution_path,
            related_evaluation_run_id=job.related_evaluation_run_id,
            latest_message=message,
            attempt_count=job.attempt_count,
            artifact_ids=job.artifact_ids,
        )
    )
    return _control_event(
        job=job,
        action_type=AsyncControlActionType.REDRIVE_QUEUED_JOB,
        requested_by=requested_by,
        approved_by=approved_by,
        reason=reason,
        resulting_status=AsyncJobStatus.QUEUED.value,
        affected_attempt_id=attempt.attempt_id,
        authorization=authorization,
    )


def quarantine_queued_async_job(
    *,
    job: AsyncRuntimeJobRecord,
    requested_by: str,
    approved_by: str,
    reason: str,
    authorization: AuthorizationDecision,
) -> AsyncRuntimeControlEventRecord:
    _require_queued_without_lease(job=job, action="quarantined")
    store = get_async_runtime_store()
    attempt = _latest_attempt(job=job)
    now = _utcnow()
    if attempt is not None:
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
                failure_reason="DELIVERY_QUARANTINED",
                recorded_message=f"Queued delivery quarantined: {reason}",
            )
        )
    store.save_job(
        AsyncRuntimeJobRecord(
            job_id=job.job_id,
            job_type=job.job_type,
            target_id=job.target_id,
            lifecycle_status=AsyncJobStatus.ABANDONED.value,
            submitted_at=job.submitted_at,
            caller_app=job.caller_app,
            correlation_id=job.correlation_id,
            payload_summary=job.payload_summary,
            execution_path=job.execution_path,
            related_evaluation_run_id=job.related_evaluation_run_id,
            latest_message=f"Queued async job quarantined: {reason}",
            attempt_count=job.attempt_count,
            artifact_ids=job.artifact_ids,
        )
    )
    return _control_event(
        job=job,
        action_type=AsyncControlActionType.QUARANTINE_QUEUED_JOB,
        requested_by=requested_by,
        approved_by=approved_by,
        reason=reason,
        resulting_status=AsyncJobStatus.ABANDONED.value,
        affected_attempt_id=None if attempt is None else attempt.attempt_id,
        authorization=authorization,
    )


def recover_unhandled_delivery(
    *,
    delivery_job_id: str,
    delivery_attempt_id: str,
    delivery_job_type: str,
    worker_id: str,
    reason: str,
) -> None:
    store = get_async_runtime_store()
    job = store.get_job(job_id=delivery_job_id)
    if job is None:
        store.save_control_event(
            _missing_delivery_control_event(
                delivery_job_id=delivery_job_id,
                delivery_attempt_id=delivery_attempt_id,
                delivery_job_type=delivery_job_type,
                worker_id=worker_id,
                reason=reason,
            )
        )
        return
    if job.lifecycle_status != AsyncJobStatus.QUEUED.value:
        return
    authorization = _system_authorization(job=job)
    if delivery_job_type not in {
        "retrieval_indexing",
        "evaluation_execution",
        "document_ingestion",
        "workflow_pack_execution",
    }:
        event = quarantine_queued_async_job(
            job=job,
            requested_by=worker_id,
            approved_by="lotus-ai.async-worker-runtime",
            reason=reason,
            authorization=authorization,
        )
    else:
        event = redrive_queued_async_job(
            job=job,
            requested_by=worker_id,
            approved_by="lotus-ai.async-worker-runtime",
            reason=reason,
            authorization=authorization,
        )
    store.save_control_event(event)


def _missing_delivery_control_event(
    *,
    delivery_job_id: str,
    delivery_attempt_id: str,
    delivery_job_type: str,
    worker_id: str,
    reason: str,
) -> AsyncRuntimeControlEventRecord:
    return AsyncRuntimeControlEventRecord(
        event_id=f"async_ctrl_evt_{uuid4().hex[:12]}",
        job_id=delivery_job_id,
        action_type=AsyncControlActionType.QUARANTINE_QUEUED_JOB.value,
        requested_by=worker_id,
        approved_by="lotus-ai.async-worker-runtime",
        reason=(
            f"Dequeued delivery referenced missing durable async job type "
            f"`{delivery_job_type}`: {reason}"
        ),
        prior_status="MISSING_RUNTIME_JOB",
        resulting_status="QUARANTINED_DELIVERY",
        affected_attempt_id=delivery_attempt_id,
        authorization=_system_authorization_for_job_type(job_type=delivery_job_type),
        recorded_at=_utcnow(),
    )


def _require_queued_without_lease(*, job: AsyncRuntimeJobRecord, action: str) -> None:
    if job.lifecycle_status != AsyncJobStatus.QUEUED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Async job '{job.job_id}' is not QUEUED and cannot be {action}.",
        )
    if get_async_runtime_store().get_active_lease(job_id=job.job_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Async job '{job.job_id}' has an active lease and cannot be {action}.",
        )


def _latest_attempt(*, job: AsyncRuntimeJobRecord) -> AsyncRuntimeAttemptRecord | None:
    attempts = get_async_runtime_store().list_attempts(job_id=job.job_id)
    return attempts[-1] if attempts else None


def _control_event(
    *,
    job: AsyncRuntimeJobRecord,
    action_type: AsyncControlActionType,
    requested_by: str,
    approved_by: str,
    reason: str,
    resulting_status: str,
    affected_attempt_id: str | None,
    authorization: AuthorizationDecision,
) -> AsyncRuntimeControlEventRecord:
    return AsyncRuntimeControlEventRecord(
        event_id=f"async_ctrl_evt_{uuid4().hex[:12]}",
        job_id=job.job_id,
        action_type=action_type.value,
        requested_by=requested_by,
        approved_by=approved_by,
        reason=reason,
        prior_status=job.lifecycle_status,
        resulting_status=resulting_status,
        affected_attempt_id=affected_attempt_id,
        authorization=authorization,
        recorded_at=_utcnow(),
    )


def _system_authorization(*, job: AsyncRuntimeJobRecord) -> AuthorizationDecision:
    return _system_authorization_for_job_type(job_type=job.job_type)


def _system_authorization_for_job_type(*, job_type: str) -> AuthorizationDecision:
    from app.contracts.access_control import (
        AuthorizationCapabilityType,
        AuthorizationOutcome,
        TenantPolicyMode,
    )

    return AuthorizationDecision(
        caller_app="lotus-ai.async-worker-runtime",
        capability_type=AuthorizationCapabilityType.ASYNC_CONTROL,
        outcome=AuthorizationOutcome.ALLOWED,
        allowed=True,
        tenant_policy_mode=TenantPolicyMode.OPTIONAL,
        task_id=None,
        requested_source_ids=[],
        effective_source_ids=[],
        tenant_id=None,
        summary=(
            "Internal async worker runtime recorded bounded delivery recovery evidence for "
            f"job type `{job_type}`."
        ),
    )


def _utcnow() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
