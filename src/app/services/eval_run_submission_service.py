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
from app.contracts.evals import (
    EvaluationRunSubmissionRequest,
    EvaluationRunSubmissionResponse,
    EvaluationRunSubmissionStatus,
)
from app.evals.fixture_manifest import (
    load_evaluation_fixture_family,
    load_evaluation_fixture_manifest,
)
from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeJobRecord,
)
from app.repositories.evaluation_runtime_repository import EvaluationRunRecord
from app.repositories.evaluation_runtime_repository import EvaluationRunAttemptRecord
from app.services.async_job_type_catalog import get_async_job_type_descriptor
from app.services.deployment_split_routing import (
    resolve_evaluation_async_route,
    resolve_evaluation_submission_route,
)
from app.services.deployment_split_shared import resolve_deployment_split_posture
from app.services.async_runtime_posture import get_async_runtime_posture
from app.services.async_runtime_store import get_async_runtime_store
from app.services.async_submission_shared import publish_async_attempt_if_configured
from app.services.evaluation_runtime_store import get_evaluation_runtime_store

RUNTIME_BACKED_EVALUATION_FIXTURE_IDS = {
    "lotus_performance_first_use_case_examples",
    "prompt_promotion_examples",
    "prompt_rollback_examples",
    "retrieval_citation_examples",
    "retrieval_embedding_examples",
    "provider_policy_examples",
    "provider_runtime_examples",
    "provider_failure_mode_examples",
    "provider_operations_examples",
    "provider_degradation_examples",
    "provider_embedding_examples",
    "safety_policy_examples",
    "safety_runtime_examples",
}


def submit_evaluation_run(
    request: EvaluationRunSubmissionRequest,
) -> EvaluationRunSubmissionResponse:
    posture = resolve_deployment_split_posture()
    route = resolve_evaluation_submission_route(
        effective_stage=posture.effective_stage,
        degraded_findings=posture.eval_degraded_findings,
    )
    submission = _submit_runtime_backed_evaluation_run(
        fixture_id=request.fixture_id,
        caller_app=request.caller_app,
        correlation_id=request.correlation_id,
        triggered_by=request.triggered_by,
    )
    if submission["submission_status"] == EvaluationRunSubmissionStatus.ACCEPTED.value:
        return EvaluationRunSubmissionResponse(
            service=settings.service_name,
            version=settings.service_version,
            delivery_phase=settings.delivery_phase,
            submission_status=EvaluationRunSubmissionStatus.ACCEPTED,
            fixture_id=request.fixture_id,
            accepted=True,
            run_id=submission["run_id"],
            async_job_id=submission["async_job_id"],
            existing_run_id=None,
            existing_async_job_id=None,
            message=(
                f"Evaluation fixture family '{request.fixture_id}' is allowlisted for durable "
                "runtime-backed submission. The run is queued in evaluation runtime state and linked "
                f"to a durable async job for the governed async execution path. {route.detail}"
            ),
        )
    if submission["submission_status"] == EvaluationRunSubmissionStatus.DUPLICATE_REJECTED.value:
        return EvaluationRunSubmissionResponse(
            service=settings.service_name,
            version=settings.service_version,
            delivery_phase=settings.delivery_phase,
            submission_status=EvaluationRunSubmissionStatus.DUPLICATE_REJECTED,
            fixture_id=request.fixture_id,
            accepted=False,
            run_id=None,
            async_job_id=None,
            existing_run_id=submission["run_id"],
            existing_async_job_id=submission["async_job_id"],
            message=(
                f"Duplicate evaluation submission rejected because active run '{submission['run_id']}' "
                f"already owns fixture family '{request.fixture_id}'. {route.detail}"
            ),
        )
    return EvaluationRunSubmissionResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        submission_status=EvaluationRunSubmissionStatus.REJECTED,
        fixture_id=request.fixture_id,
        accepted=False,
        run_id=None,
        async_job_id=None,
        existing_run_id=None,
        existing_async_job_id=None,
        message=f"{submission['message']} {route.detail}",
    )


def submit_evaluation_execution_async_job(
    request: AsyncJobSubmissionRequest,
) -> AsyncJobSubmissionResponse:
    posture = resolve_deployment_split_posture()
    route = resolve_evaluation_async_route(
        effective_stage=posture.effective_stage,
        degraded_findings=posture.eval_degraded_findings,
    )
    fixture_id = _validate_evaluation_fixture_target(target_id=request.target_id)
    submission = _submit_runtime_backed_evaluation_run(
        fixture_id=fixture_id,
        caller_app=request.caller_app,
        correlation_id=request.correlation_id,
        triggered_by=request.caller_app,
    )
    if submission["submission_status"] == EvaluationRunSubmissionStatus.ACCEPTED.value:
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
            target_id=fixture_id,
            existing_job_id=None,
            accepted=True,
            job_id=submission["async_job_id"],
            message=(
                f"Evaluation fixture family '{fixture_id}' is allowlisted for durable runtime-backed "
                "submission and governed async execution. The async job is linked to an authoritative "
                f"evaluation run record. {route.detail}"
            ),
        )
    if submission["submission_status"] == EvaluationRunSubmissionStatus.DUPLICATE_REJECTED.value:
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
            target_id=fixture_id,
            existing_job_id=submission["async_job_id"],
            accepted=False,
            job_id=None,
            message=(
                f"Duplicate async evaluation submission rejected because active evaluation run "
                f"'{submission['run_id']}' already owns fixture family '{fixture_id}'. {route.detail}"
            ),
        )
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
        target_id=fixture_id,
        existing_job_id=None,
        accepted=False,
        job_id=None,
        message=f"{submission['message']} {route.detail}",
    )


def _submit_runtime_backed_evaluation_run(
    *,
    fixture_id: str,
    caller_app: str,
    correlation_id: str,
    triggered_by: str,
) -> dict[str, str]:
    fixture_family = load_evaluation_fixture_family(fixture_id=fixture_id)
    _require_allowlisted_runtime_fixture(fixture_id=fixture_id)
    existing_run = _find_active_duplicate_runtime_run(fixture_id=fixture_id)
    if existing_run is not None:
        return {
            "submission_status": EvaluationRunSubmissionStatus.DUPLICATE_REJECTED.value,
            "run_id": existing_run.run_id,
            "async_job_id": existing_run.async_job_id or "",
            "message": "Active runtime-backed evaluation run already exists for this fixture family.",
        }

    submitted_at = _utcnow().isoformat().replace("+00:00", "Z")
    run_id = f"evalrun_{uuid4().hex[:12]}"
    async_job_id = f"asyncjob_evaluation_execution_{uuid4().hex[:12]}"
    job_type = get_async_job_type_descriptor(job_type="evaluation_execution")
    if job_type is None or not job_type.enabled:
        return {
            "submission_status": EvaluationRunSubmissionStatus.REJECTED.value,
            "message": "Evaluation execution is not allowlisted for runtime-backed submission.",
        }

    get_evaluation_runtime_store().save_run(
        EvaluationRunRecord(
            run_id=run_id,
            fixture_id=fixture_id,
            manifest_version=load_evaluation_fixture_manifest().manifest_version,
            lifecycle_status=AsyncJobStatus.QUEUED.value,
            triggered_by=triggered_by,
            submitted_at=submitted_at,
            async_job_id=async_job_id,
            latest_message=(
                f"Evaluation fixture family '{fixture_id}' accepted into durable runtime state and "
                "queued for governed async evaluation execution."
            ),
            verdict=None,
            case_count=len(fixture_family.cases),
        )
    )
    get_evaluation_runtime_store().save_attempt(
        EvaluationRunAttemptRecord(
            attempt_id=f"{run_id}_attempt_001",
            run_id=run_id,
            attempt_number=1,
            lifecycle_status=AsyncJobStatus.QUEUED.value,
            started_at=None,
            completed_at=None,
            worker_id=None,
            latest_message="Initial runtime-backed evaluation attempt queued.",
            verdict=None,
            failure_reason=None,
        )
    )
    job_record = AsyncRuntimeJobRecord(
        job_id=async_job_id,
        job_type="evaluation_execution",
        target_id=fixture_id,
        lifecycle_status=AsyncJobStatus.QUEUED.value,
        submitted_at=submitted_at,
        caller_app=caller_app,
        correlation_id=correlation_id,
        payload_summary=f"Run evaluation fixture family '{fixture_id}'.",
        execution_path=job_type.execution_path,
        related_evaluation_run_id=run_id,
        latest_message=f"Evaluation execution job linked to runtime-backed run '{run_id}' is queued.",
        attempt_count=1,
        artifact_ids=[],
    )
    attempt_record = AsyncRuntimeAttemptRecord(
        attempt_id=f"{async_job_id}_attempt_001",
        job_id=async_job_id,
        attempt_number=1,
        lifecycle_status="SUBMITTED",
        worker_id=None,
        claimed_at=None,
        heartbeat_at=None,
        started_at=None,
        completed_at=None,
        failure_reason=None,
        recorded_message="Initial runtime-backed evaluation submission recorded.",
    )
    get_async_runtime_store().save_job(job_record)
    get_async_runtime_store().save_attempt(attempt_record)
    publish_async_attempt_if_configured(job=job_record, attempt=attempt_record)
    return {
        "submission_status": EvaluationRunSubmissionStatus.ACCEPTED.value,
        "run_id": run_id,
        "async_job_id": async_job_id,
    }


def _require_allowlisted_runtime_fixture(*, fixture_id: str) -> None:
    if fixture_id not in RUNTIME_BACKED_EVALUATION_FIXTURE_IDS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Evaluation fixture family '{fixture_id}' remains staged-only and is not yet "
                "allowlisted for runtime-backed execution submission."
            ),
        )


def _validate_evaluation_fixture_target(*, target_id: str | None) -> str:
    if not target_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Async evaluation_execution submission requires a concrete evaluation fixture target_id.",
        )
    try:
        load_evaluation_fixture_family(fixture_id=target_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown evaluation fixture family: {target_id}",
        ) from exc
    return target_id


def _find_active_duplicate_runtime_run(*, fixture_id: str) -> EvaluationRunRecord | None:
    for record in reversed(get_evaluation_runtime_store().list_runs()):
        if record.fixture_id != fixture_id:
            continue
        if record.lifecycle_status not in {
            AsyncJobStatus.QUEUED.value,
            AsyncJobStatus.CLAIMED.value,
            AsyncJobStatus.RUNNING.value,
        }:
            continue
        return record
    return None


def _utcnow() -> datetime:
    return datetime.now(UTC)
