from __future__ import annotations

from dataclasses import dataclass

from app.services.eval_attempt_runtime import fail_active_evaluation_attempt
from app.services.async_worker_runtime import (
    AsyncWorkerClaimResult,
    claim_async_job_by_id,
    claim_next_async_job_for_types,
    complete_async_job,
    fail_async_job,
    start_async_job,
)
from app.services.eval_runtime_execution import execute_runtime_backed_evaluation_run


@dataclass(frozen=True)
class EvaluationAsyncExecutionResult:
    async_job_id: str
    evaluation_run_id: str
    verdict: str
    case_result_count: int


def run_next_evaluation_execution_job(*, worker_id: str) -> EvaluationAsyncExecutionResult | None:
    claim = claim_next_async_job_for_types(
        worker_id=worker_id,
        job_types=("evaluation_execution",),
    )
    if claim is None:
        return None
    return _execute_claimed_evaluation_job(claim=claim, worker_id=worker_id)


def run_evaluation_execution_job_by_id(
    *,
    async_job_id: str,
    worker_id: str,
) -> EvaluationAsyncExecutionResult | None:
    claim = claim_async_job_by_id(job_id=async_job_id, worker_id=worker_id)
    if claim is None:
        return None
    return _execute_claimed_evaluation_job(claim=claim, worker_id=worker_id)


def _execute_claimed_evaluation_job(
    *,
    claim: AsyncWorkerClaimResult,
    worker_id: str,
) -> EvaluationAsyncExecutionResult | None:
    if claim.job.job_type != "evaluation_execution" or claim.job.related_evaluation_run_id is None:
        fail_async_job(
            job_id=claim.job.job_id,
            worker_id=worker_id,
            failure_reason="UNSUPPORTED_ASYNC_JOB_TYPE",
            retryable=False,
        )
        return None

    start_async_job(job_id=claim.job.job_id, worker_id=worker_id)
    try:
        result = execute_runtime_backed_evaluation_run(
            run_id=claim.job.related_evaluation_run_id,
            worker_id=worker_id,
        )
    except Exception as exc:
        fail_async_job(
            job_id=claim.job.job_id,
            worker_id=worker_id,
            failure_reason=type(exc).__name__,
            retryable=False,
        )
        fail_active_evaluation_attempt(
            run_id=claim.job.related_evaluation_run_id,
            reason_message=(
                f"Runtime-backed evaluation execution failed with {type(exc).__name__}."
            ),
            failure_reason=type(exc).__name__,
        )
        raise

    completion_message = (
        f"Runtime-backed evaluation execution completed with verdict '{result.verdict.value}'."
    )
    complete_async_job(
        job_id=claim.job.job_id,
        worker_id=worker_id,
        message=completion_message,
    )
    return EvaluationAsyncExecutionResult(
        async_job_id=claim.job.job_id,
        evaluation_run_id=result.run_id,
        verdict=result.verdict.value,
        case_result_count=result.case_result_count,
    )
