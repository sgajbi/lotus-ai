from __future__ import annotations

from dataclasses import dataclass

from app.contracts.async_runtime import AsyncJobSubmissionRequest, AsyncJobSubmissionResponse
from app.contracts.providers import EmbeddingExecutionRequest
from app.contracts.retrieval import (
    RetrievalIndexJobDescriptor,
    RetrievalIndexStatus,
    RetrievalJobStatus,
)
from app.providers.base import ProviderExecutionError
from app.services.async_submission_service import submit_async_job
from app.services.async_worker_runtime import (
    AsyncWorkerClaimResult,
    claim_async_job_by_id,
    claim_next_async_job_for_types,
    complete_async_job,
    fail_async_job,
    start_async_job,
)
from app.services.embedding_provider_gateway import execute_embedding_generation
from app.services.retrieval_catalog_service import get_retrieval_job_detail_or_raise
from app.services.retrieval_store import get_retrieval_repository


@dataclass(frozen=True)
class RetrievalAsyncExecutionResult:
    async_job_id: str
    retrieval_job_id: str
    source_id: str
    terminal_status: str


def submit_retrieval_index_job_async(
    *,
    job_id: str,
    caller_app: str,
    correlation_id: str,
) -> AsyncJobSubmissionResponse:
    retrieval_job = get_retrieval_job_detail_or_raise(job_id)
    return submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id=job_id,
            caller_app=caller_app,
            correlation_id=correlation_id,
            payload_summary=(
                f"Runtime-backed retrieval indexing for source '{retrieval_job.job.source_id}'."
            ),
        )
    )


def run_next_retrieval_index_job(*, worker_id: str) -> RetrievalAsyncExecutionResult | None:
    claim = claim_next_async_job_for_types(
        worker_id=worker_id,
        job_types=("retrieval_indexing",),
    )
    if claim is None:
        return None
    return _execute_claimed_retrieval_index_job(claim=claim, worker_id=worker_id)


def run_retrieval_index_job_by_id(
    *,
    async_job_id: str,
    worker_id: str,
) -> RetrievalAsyncExecutionResult | None:
    claim = claim_async_job_by_id(job_id=async_job_id, worker_id=worker_id)
    if claim is None:
        return None
    return _execute_claimed_retrieval_index_job(claim=claim, worker_id=worker_id)


def _execute_claimed_retrieval_index_job(
    *,
    claim: AsyncWorkerClaimResult,
    worker_id: str,
) -> RetrievalAsyncExecutionResult | None:
    if claim.job.job_type != "retrieval_indexing" or claim.job.target_id is None:
        fail_async_job(
            job_id=claim.job.job_id,
            worker_id=worker_id,
            failure_reason="UNSUPPORTED_ASYNC_JOB_TYPE",
            retryable=False,
        )
        return None

    retrieval_job = get_retrieval_job_detail_or_raise(claim.job.target_id)
    repository = get_retrieval_repository()
    start_async_job(job_id=claim.job.job_id, worker_id=worker_id)
    repository.save_index_job(
        RetrievalIndexJobDescriptor(
            job_id=retrieval_job.job.job_id,
            source_id=retrieval_job.job.source_id,
            status=RetrievalJobStatus.RUNNING,
            document_count=retrieval_job.job.document_count,
            chunk_count=retrieval_job.job.chunk_count,
            message=(
                f"Runtime-backed retrieval indexing is executing under async job '{claim.job.job_id}'."
            ),
        )
    )
    try:
        _run_embedding_generation_for_source(
            source_id=retrieval_job.job.source_id,
            caller_app=claim.job.caller_app,
        )
    except ProviderExecutionError as exc:
        fail_async_job(
            job_id=claim.job.job_id,
            worker_id=worker_id,
            failure_reason=exc.category.value,
            retryable=False,
        )
        return RetrievalAsyncExecutionResult(
            async_job_id=claim.job.job_id,
            retrieval_job_id=retrieval_job.job.job_id,
            source_id=retrieval_job.job.source_id,
            terminal_status=RetrievalJobStatus.FAILED.value,
        )
    repository.set_source_index_status(
        source_id=retrieval_job.job.source_id,
        index_status=RetrievalIndexStatus.INDEXED.value,
    )
    completion_message = (
        f"Runtime-backed retrieval indexing completed successfully for source "
        f"'{retrieval_job.job.source_id}'."
    )
    repository.save_index_job(
        RetrievalIndexJobDescriptor(
            job_id=retrieval_job.job.job_id,
            source_id=retrieval_job.job.source_id,
            status=RetrievalJobStatus.COMPLETED,
            document_count=retrieval_job.job.document_count,
            chunk_count=retrieval_job.job.chunk_count,
            message=completion_message,
        )
    )
    complete_async_job(
        job_id=claim.job.job_id,
        worker_id=worker_id,
        message=completion_message,
    )
    return RetrievalAsyncExecutionResult(
        async_job_id=claim.job.job_id,
        retrieval_job_id=retrieval_job.job.job_id,
        source_id=retrieval_job.job.source_id,
        terminal_status=RetrievalJobStatus.COMPLETED.value,
    )


def _run_embedding_generation_for_source(*, source_id: str, caller_app: str) -> None:
    repository = get_retrieval_repository()
    documents = repository.list_documents_for_source(source_id)
    for document in documents:
        chunks = repository.list_chunks_for_document(document.document_id)
        representative_text = " ".join(
            [document.title, *(chunk.preview for chunk in chunks[:2])]
        ).strip()
        if not representative_text:
            representative_text = document.title
        execute_embedding_generation(
            EmbeddingExecutionRequest(
                caller_app=caller_app,
                corpus_id=source_id,
                content=representative_text,
                metadata={
                    "source_id": source_id,
                    "document_id": document.document_id,
                    "chunk_count": len(chunks),
                },
            )
        )
