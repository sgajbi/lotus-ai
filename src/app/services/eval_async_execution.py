from __future__ import annotations

from dataclasses import dataclass

from app.repositories.evaluation_runtime_repository import EvaluationRunRecord
from app.services.async_worker_runtime import (
    claim_next_async_job_for_types,
    complete_async_job,
    fail_async_job,
    start_async_job,
)
from app.services.eval_runtime_execution import execute_runtime_backed_evaluation_run
from app.services.evaluation_runtime_store import get_evaluation_runtime_store


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
        run = get_evaluation_runtime_store().get_run(run_id=claim.job.related_evaluation_run_id)
        if run is not None:
            get_evaluation_runtime_store().save_run(
                EvaluationRunRecord(
                    run_id=run.run_id,
                    fixture_id=run.fixture_id,
                    manifest_version=run.manifest_version,
                    lifecycle_status="FAILED",
                    triggered_by=run.triggered_by,
                    submitted_at=run.submitted_at,
                    async_job_id=run.async_job_id,
                    latest_message=f"Runtime-backed evaluation execution failed with {type(exc).__name__}.",
                    verdict=None,
                    case_count=run.case_count,
                )
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
