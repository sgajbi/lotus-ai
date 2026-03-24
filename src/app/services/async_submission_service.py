from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.async_runtime import (
    AsyncJobStatus,
    AsyncJobSubmissionRequest,
    AsyncJobSubmissionResponse,
    AsyncSubmissionStatus,
)
from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeJobRecord,
)
from app.services.retrieval_catalog_service import get_retrieval_job_detail_or_raise
from app.services.retrieval_catalog_service import get_retrieval_ingestion_job_detail_or_raise
from app.services.async_job_type_catalog import get_async_job_type_descriptor
from app.services.deployment_split_routing import resolve_retrieval_async_route
from app.services.deployment_split_shared import resolve_deployment_split_posture
from app.services.async_runtime_posture import get_async_runtime_posture
from app.services.async_runtime_store import get_async_runtime_store
from app.services.async_submission_shared import publish_async_attempt_if_configured
from app.services.eval_run_submission_service import submit_evaluation_execution_async_job


def submit_async_job(request: AsyncJobSubmissionRequest) -> AsyncJobSubmissionResponse:
    posture = resolve_deployment_split_posture()
    retrieval_async_route = resolve_retrieval_async_route(
        effective_stage=posture.effective_stage,
        degraded_findings=posture.retrieval_degraded_findings,
    )
    if request.job_type == "evaluation_execution":
        return submit_evaluation_execution_async_job(request)
    job_type = get_async_job_type_descriptor(job_type=request.job_type)
    if job_type is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown lotus-ai async job type: {request.job_type}",
        )

    if not job_type.enabled:
        async_posture = get_async_runtime_posture()
        return AsyncJobSubmissionResponse(
            service=settings.service_name,
            version=settings.service_version,
            delivery_phase=settings.delivery_phase,
            submission_status=AsyncSubmissionStatus.REJECTED,
            cutover_state=async_posture.cutover_state,
            queue_mode=async_posture.queue_mode,
            worker_mode=async_posture.worker_mode,
            job_type=request.job_type,
            target_id=request.target_id,
            existing_job_id=None,
            accepted=False,
            job_id=None,
            message=(
                f"Async job type '{request.job_type}' remains staged-only in the current phase and "
                "is not yet allowlisted for durable runtime-backed submission and stubbed worker handling. "
                f"{retrieval_async_route.detail if request.job_type == 'retrieval_indexing' else ''}".strip()
            ),
        )
    _validate_async_job_target(request=request)
    duplicate_job = _find_active_duplicate_submission(request=request)
    if duplicate_job is not None:
        async_posture = get_async_runtime_posture()
        return AsyncJobSubmissionResponse(
            service=settings.service_name,
            version=settings.service_version,
            delivery_phase=settings.delivery_phase,
            submission_status=AsyncSubmissionStatus.DUPLICATE_REJECTED,
            cutover_state=async_posture.cutover_state,
            queue_mode=async_posture.queue_mode,
            worker_mode=async_posture.worker_mode,
            job_type=request.job_type,
            target_id=request.target_id,
            existing_job_id=duplicate_job.job_id,
            accepted=False,
            job_id=None,
            message=(
                f"Duplicate async submission rejected because active job '{duplicate_job.job_id}' "
                f"already owns {request.job_type} for target '{request.target_id}'. "
                f"{retrieval_async_route.detail if request.job_type == 'retrieval_indexing' else ''}".strip()
            ),
        )
    submitted_at = _utcnow().isoformat().replace("+00:00", "Z")
    job_id = f"asyncjob_{request.job_type}_{uuid4().hex[:12]}"
    attempt_id = f"{job_id}_attempt_001"
    store = get_async_runtime_store()
    job_record = AsyncRuntimeJobRecord(
        job_id=job_id,
        job_type=request.job_type,
        target_id=request.target_id,
        lifecycle_status=AsyncJobStatus.QUEUED.value,
        submitted_at=submitted_at,
        caller_app=request.caller_app,
        correlation_id=request.correlation_id,
        payload_summary=request.payload_summary,
        execution_path=job_type.execution_path,
        related_evaluation_run_id=None,
        latest_message="Job accepted into durable async runtime state.",
        attempt_count=1,
        artifact_ids=[],
    )
    attempt_record = AsyncRuntimeAttemptRecord(
        attempt_id=attempt_id,
        job_id=job_id,
        attempt_number=1,
        lifecycle_status="SUBMITTED",
        worker_id=None,
        claimed_at=None,
        heartbeat_at=None,
        started_at=None,
        completed_at=None,
        failure_reason=None,
        recorded_message="Initial durable async submission recorded.",
    )
    store.save_job(job_record)
    store.save_attempt(attempt_record)
    delivery_published = publish_async_attempt_if_configured(
        job=job_record,
        attempt=attempt_record,
    )
    async_posture = get_async_runtime_posture()

    return AsyncJobSubmissionResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        submission_status=AsyncSubmissionStatus.ACCEPTED,
        cutover_state=async_posture.cutover_state,
        queue_mode=async_posture.queue_mode,
        worker_mode=async_posture.worker_mode,
        job_type=request.job_type,
        target_id=request.target_id,
        existing_job_id=None,
        accepted=True,
        job_id=job_id,
        message=(
            f"Async job type '{request.job_type}' is allowlisted for durable submission. The job "
            + (
                "was also published to the managed queue path for dedicated worker execution."
                if delivery_published
                else "is recorded in the authoritative async state store while in-process execution remains primary."
            )
            + (
                f" {retrieval_async_route.detail}"
                if request.job_type == "retrieval_indexing"
                else ""
            )
        ),
    )


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _validate_async_job_target(*, request: AsyncJobSubmissionRequest) -> None:
    if request.job_type not in {"retrieval_indexing", "document_ingestion"}:
        return
    if not request.target_id:
        detail = (
            "Async retrieval_indexing submission requires a concrete retrieval index job target_id."
            if request.job_type == "retrieval_indexing"
            else "Async document_ingestion submission requires a concrete retrieval ingestion job target_id."
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
    if request.job_type == "retrieval_indexing":
        get_retrieval_job_detail_or_raise(request.target_id)
        return
    get_retrieval_ingestion_job_detail_or_raise(request.target_id)


def _find_active_duplicate_submission(
    *, request: AsyncJobSubmissionRequest
) -> AsyncRuntimeJobRecord | None:
    if request.job_type not in {"retrieval_indexing", "document_ingestion"} or request.target_id is None:
        return None
    active_statuses = {
        AsyncJobStatus.QUEUED.value,
        AsyncJobStatus.CLAIMED.value,
        AsyncJobStatus.RUNNING.value,
    }
    for record in reversed(get_async_runtime_store().list_jobs()):
        if record.job_type != request.job_type:
            continue
        if record.target_id != request.target_id:
            continue
        if record.caller_app != request.caller_app:
            continue
        if record.lifecycle_status not in active_statuses:
            continue
        return record
    return None
