from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, status

from app.contracts.async_runtime import AsyncJobSubmissionRequest, AsyncJobSubmissionResponse
from app.contracts.retrieval import (
    RetrievalIngestionAction,
    RetrievalIngestionJobDescriptor,
    RetrievalIngestionJobStatus,
    RetrievalIndexJobDescriptor,
    RetrievalJobStatus,
)
from app.services.async_submission_service import submit_async_job
from app.services.async_worker_runtime import (
    AsyncWorkerClaimResult,
    claim_async_job_by_id,
    claim_next_async_job_for_types,
    complete_async_job,
    fail_async_job,
    start_async_job,
)
from app.services.retrieval_catalog_service import get_retrieval_ingestion_job_detail_or_raise
from app.services.retrieval_ingestion_artifacts import (
    persist_retrieval_ingestion_diagnostic_artifact,
)
from app.services.retrieval_async_execution import submit_retrieval_index_job_async
from app.services.retrieval_store import get_retrieval_repository


@dataclass(frozen=True)
class RetrievalIngestionAsyncExecutionResult:
    async_job_id: str
    ingestion_job_id: str
    source_id: str
    terminal_status: str


def submit_retrieval_ingestion_job_async(
    *,
    job_id: str,
    caller_app: str,
    correlation_id: str,
) -> AsyncJobSubmissionResponse:
    ingestion_job = get_retrieval_ingestion_job_detail_or_raise(job_id).job
    if ingestion_job.status == RetrievalIngestionJobStatus.BLOCKED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Retrieval ingestion job '{job_id}' is blocked and cannot be submitted into the async runtime."
            ),
        )
    return submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="document_ingestion",
            target_id=job_id,
            caller_app=caller_app,
            correlation_id=correlation_id,
            payload_summary=(
                f"Runtime-backed retrieval ingestion for source '{ingestion_job.source_id}'."
            ),
        )
    )


def run_next_retrieval_ingestion_job(
    *, worker_id: str
) -> RetrievalIngestionAsyncExecutionResult | None:
    claim = claim_next_async_job_for_types(
        worker_id=worker_id,
        job_types=("document_ingestion",),
    )
    if claim is None:
        return None
    return _execute_claimed_retrieval_ingestion_job(claim=claim, worker_id=worker_id)


def run_retrieval_ingestion_job_by_id(
    *,
    async_job_id: str,
    worker_id: str,
) -> RetrievalIngestionAsyncExecutionResult | None:
    claim = claim_async_job_by_id(job_id=async_job_id, worker_id=worker_id)
    if claim is None:
        return None
    return _execute_claimed_retrieval_ingestion_job(claim=claim, worker_id=worker_id)


def _execute_claimed_retrieval_ingestion_job(
    *,
    claim: AsyncWorkerClaimResult,
    worker_id: str,
) -> RetrievalIngestionAsyncExecutionResult | None:
    if claim.job.job_type != "document_ingestion" or claim.job.target_id is None:
        fail_async_job(
            job_id=claim.job.job_id,
            worker_id=worker_id,
            failure_reason="UNSUPPORTED_ASYNC_JOB_TYPE",
            retryable=False,
        )
        return None

    repository = get_retrieval_repository()
    ingestion_job = get_retrieval_ingestion_job_detail_or_raise(claim.job.target_id).job
    if (
        ingestion_job.target_version_id is None
        or ingestion_job.status == RetrievalIngestionJobStatus.BLOCKED
    ):
        failed_job = _updated_ingestion_job(
            ingestion_job,
            status=RetrievalIngestionJobStatus.FAILED,
            message="Ingestion execution is blocked because the target document version is not eligible.",
        )
        repository.save_ingestion_job(failed_job)
        persist_retrieval_ingestion_diagnostic_artifact(
            job=failed_job,
            created_at=_utcnow_isoformat(),
            created_by=worker_id,
            runtime_async_job_id=claim.job.job_id,
            follow_on_async_job_id=None,
        )
        fail_async_job(
            job_id=claim.job.job_id,
            worker_id=worker_id,
            failure_reason="INGESTION_TARGET_BLOCKED",
            retryable=False,
        )
        return RetrievalIngestionAsyncExecutionResult(
            async_job_id=claim.job.job_id,
            ingestion_job_id=ingestion_job.job_id,
            source_id=ingestion_job.source_id,
            terminal_status=RetrievalIngestionJobStatus.FAILED.value,
        )

    start_async_job(job_id=claim.job.job_id, worker_id=worker_id)
    repository.save_ingestion_job(
        _updated_ingestion_job(
            ingestion_job,
            status=RetrievalIngestionJobStatus.RUNNING,
            message=(
                f"Runtime-backed retrieval ingestion is executing under async job '{claim.job.job_id}'."
            ),
        )
    )

    try:
        _apply_ingestion_effects(ingestion_job)
        follow_on_submission = submit_retrieval_index_job_async(
            job_id=f"retjob_{ingestion_job.source_id.replace('-', '_')}",
            caller_app=claim.job.caller_app,
            correlation_id=claim.job.correlation_id,
        )
    except Exception as exc:
        failed_job = _updated_ingestion_job(
            ingestion_job,
            status=RetrievalIngestionJobStatus.FAILED,
            message=f"Ingestion execution failed: {exc}",
        )
        repository.save_ingestion_job(failed_job)
        persist_retrieval_ingestion_diagnostic_artifact(
            job=failed_job,
            created_at=_utcnow_isoformat(),
            created_by=worker_id,
            runtime_async_job_id=claim.job.job_id,
            follow_on_async_job_id=None,
        )
        fail_async_job(
            job_id=claim.job.job_id,
            worker_id=worker_id,
            failure_reason="INGESTION_EXECUTION_FAILED",
            retryable=False,
        )
        return RetrievalIngestionAsyncExecutionResult(
            async_job_id=claim.job.job_id,
            ingestion_job_id=ingestion_job.job_id,
            source_id=ingestion_job.source_id,
            terminal_status=RetrievalIngestionJobStatus.FAILED.value,
        )

    if follow_on_submission.accepted and follow_on_submission.job_id is not None:
        follow_on_message = (
            f"Follow-on retrieval indexing async job '{follow_on_submission.job_id}' was queued."
        )
    elif follow_on_submission.existing_job_id is not None:
        follow_on_message = f"Follow-on retrieval indexing reused active async job '{follow_on_submission.existing_job_id}'."
    else:
        follow_on_message = follow_on_submission.message

    completion_message = (
        f"Runtime-backed ingestion completed for source '{ingestion_job.source_id}'. "
        f"{follow_on_message}"
    )
    completed_job = _updated_ingestion_job(
        ingestion_job,
        status=RetrievalIngestionJobStatus.COMPLETED,
        message=completion_message,
    )
    repository.save_ingestion_job(completed_job)
    persist_retrieval_ingestion_diagnostic_artifact(
        job=completed_job,
        created_at=_utcnow_isoformat(),
        created_by=worker_id,
        runtime_async_job_id=claim.job.job_id,
        follow_on_async_job_id=(
            follow_on_submission.job_id or follow_on_submission.existing_job_id
        ),
    )
    complete_async_job(
        job_id=claim.job.job_id,
        worker_id=worker_id,
        message=completion_message,
    )
    return RetrievalIngestionAsyncExecutionResult(
        async_job_id=claim.job.job_id,
        ingestion_job_id=ingestion_job.job_id,
        source_id=ingestion_job.source_id,
        terminal_status=RetrievalIngestionJobStatus.COMPLETED.value,
    )


def _apply_ingestion_effects(job: RetrievalIngestionJobDescriptor) -> None:
    repository = get_retrieval_repository()
    repository.set_source_index_status(
        source_id=job.source_id,
        index_status="STAGED",
    )
    action_note = {
        RetrievalIngestionAction.ONBOARD: "Document onboarding completed and the source now requires indexing.",
        RetrievalIngestionAction.REFRESH: "Document refresh completed and the source now requires reindexing.",
        RetrievalIngestionAction.WITHDRAW: "Document withdrawal completed and the source now requires reindexing.",
    }[job.requested_action]
    repository.save_index_job(
        RetrievalIndexJobDescriptor(
            job_id=f"retjob_{job.source_id.replace('-', '_')}",
            source_id=job.source_id,
            status=RetrievalJobStatus.STAGED,
            document_count=len(repository.list_documents_for_source(job.source_id)),
            chunk_count=sum(
                len(repository.list_chunks_for_document(document.document_id))
                for document in repository.list_documents_for_source(job.source_id)
            ),
            message=(
                f"{action_note} Follow-on indexing is governed through the existing retrieval indexing path."
            ),
        )
    )


def _updated_ingestion_job(
    job: RetrievalIngestionJobDescriptor,
    *,
    status: RetrievalIngestionJobStatus,
    message: str,
) -> RetrievalIngestionJobDescriptor:
    return job.model_copy(
        update={
            "status": status,
            "message": message,
        }
    )


def _utcnow_isoformat() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
