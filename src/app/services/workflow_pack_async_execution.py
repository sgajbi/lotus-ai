from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from threading import RLock
from uuid import uuid4

from fastapi import HTTPException, status

from app.services.kill_switch_control import (
    drain_completion_permit,
    enforce_kill_switch_intake,
)
from app.config import settings
from app.contracts.artifacts import ArtifactDescriptor
from app.contracts.async_runtime import AsyncJobStatus
from app.contracts.workflow_pack_queue_policies import (
    WorkflowPackQueueEventDescriptor,
    WorkflowPackQueueEventType,
    WorkflowPackQueueLane,
    WorkflowPackQueuePolicyDescriptor,
    WorkflowPackQueueState,
    is_workflow_pack_queue_state_transition_allowed,
)
from app.contracts.workflow_packs import (
    WorkflowPackAsyncExecutionSubmissionResponse,
    WorkflowPackEligibilityEvaluationRequest,
    WorkflowPackExecutionRequest,
    WorkflowPackRegistrationDescriptor,
)
from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeJobRecord,
)
from app.services.artifact_payloads import load_artifact_descriptors
from app.services.async_job_mapping import map_async_runtime_job
from app.services.async_runtime_store import get_async_runtime_store
from app.services.async_submission_shared import publish_async_attempt_if_configured
from app.services.async_worker_runtime import (
    AsyncWorkerClaimResult,
    claim_async_job_by_id,
    claim_next_async_job_for_types,
    complete_async_job,
    fail_async_job,
    start_async_job,
)
from app.services.task_execution_pipeline import validate_task_request
from app.services.workflow_pack_activation import evaluate_workflow_pack_eligibility
from app.services.workflow_pack_bindings import (
    get_resolved_workflow_pack_execution_binding,
)
from app.services.workflow_pack_execution import (
    execute_workflow_pack,
    validate_workflow_pack_execution_binding,
)
from app.services.workflow_pack_queue_events import (
    WorkflowPackQueueEventStoreNotReadyError,
    build_workflow_pack_queue_event_detail,
    ensure_workflow_pack_queue_event_store_ready,
    record_workflow_pack_queue_event,
)
from app.services.workflow_pack_queue_policy_catalog import (
    get_workflow_pack_queue_policy_descriptor,
)
from app.services.workflow_pack_queue_request_snapshots import (
    QUEUE_REQUEST_SNAPSHOT_ARTIFACT_TYPE,
    build_workflow_pack_execution_request_from_queue_snapshot,
    load_workflow_pack_queue_request_snapshot_payload,
    persist_workflow_pack_queue_request_snapshot,
)
from app.services.workflow_pack_run_ledger import ensure_workflow_pack_run_store_ready
from app.services.workflow_pack_task_flow_service import ensure_workflow_pack_task_flow_store_ready

WORKFLOW_PACK_EXECUTION_ASYNC_JOB_TYPE = "workflow_pack_execution"
_ACTIVE_ASYNC_JOB_STATUSES = {
    AsyncJobStatus.QUEUED.value,
    AsyncJobStatus.CLAIMED.value,
    AsyncJobStatus.RUNNING.value,
}
_async_submission_idempotency_lock = RLock()


@dataclass(frozen=True)
class WorkflowPackAsyncExecutionResult:
    async_job_id: str
    queue_item_id: str
    workflow_pack_run_id: str | None
    terminal_status: str


def submit_workflow_pack_execution_async(
    request: WorkflowPackExecutionRequest,
) -> WorkflowPackAsyncExecutionSubmissionResponse:
    resolved = _preflight_workflow_pack_execution_request(request=request)
    queue_item_id = f"wpq_{uuid4().hex}"
    lane = request.queue_lane or resolved.policy.default_lane
    _validate_lane(policy=resolved.policy, lane=lane)
    idempotency_key = _build_async_submission_idempotency_key(request=request)
    request_fingerprint = _fingerprint_async_execution_request(
        request=request,
        lane=lane,
        workflow_surface=resolved.workflow_surface,
    )
    with _async_submission_idempotency_lock:
        existing_response = _resolve_existing_idempotent_async_submission(
            request=request,
            policy=resolved.policy,
            workflow_surface=resolved.workflow_surface,
            request_fingerprint=request_fingerprint,
            idempotency_key=idempotency_key,
        )
        if existing_response is not None:
            return existing_response
        _reject_duplicate_active_submission(request=request, policy=resolved.policy)
        _enforce_queued_capacity(policy=resolved.policy, lane=lane)

        now = _utc_now_timestamp()
        snapshot_ref = persist_workflow_pack_queue_request_snapshot(
            queue_item_id=queue_item_id,
            registration=resolved.registration,
            lane=lane,
            task_request=request.task_request,
            workflow_surface=resolved.workflow_surface,
            environment=request.environment,
            caller_identity_class=request.caller_identity_class,
            created_at=now,
            idempotency_key=idempotency_key,
            idempotency_request_fingerprint=request_fingerprint,
        )
        requested_event = _record_queue_event(
            queue_item_id=queue_item_id,
            event_type=WorkflowPackQueueEventType.ADMISSION_REQUESTED,
            policy=resolved.policy,
            lane=lane,
            state=WorkflowPackQueueState.NOT_ADMITTED,
            request=request,
            workflow_surface=resolved.workflow_surface,
            artifact_refs=[snapshot_ref],
            idempotency_key=idempotency_key,
            idempotency_request_fingerprint=request_fingerprint,
            message=(
                "Workflow-pack async execution requested durable queued-worker posture for "
                f"`{request.pack_id}@{request.version}`."
            ),
        )
        queued_event = _record_queue_event(
            queue_item_id=queue_item_id,
            event_type=WorkflowPackQueueEventType.ADMISSION_QUEUED,
            policy=resolved.policy,
            lane=lane,
            state=_transition(
                current_state=requested_event.state,
                next_state=WorkflowPackQueueState.QUEUED,
            ),
            request=request,
            workflow_surface=resolved.workflow_surface,
            artifact_refs=[snapshot_ref],
            idempotency_key=idempotency_key,
            idempotency_request_fingerprint=request_fingerprint,
            message=(
                "Workflow-pack async execution queued in durable async runtime state for "
                f"`{request.pack_id}@{request.version}`."
            ),
        )

        job_id = f"asyncjob_workflow_pack_execution_{uuid4().hex[:12]}"
        attempt_id = f"{job_id}_attempt_001"
        job_record = AsyncRuntimeJobRecord(
            job_id=job_id,
            job_type=WORKFLOW_PACK_EXECUTION_ASYNC_JOB_TYPE,
            target_id=queue_item_id,
            lifecycle_status=AsyncJobStatus.QUEUED.value,
            submitted_at=now,
            caller_app=request.task_request.caller.caller_app,
            correlation_id=request.task_request.caller.correlation_id,
            payload_summary=(
                f"Durable workflow-pack execution for {request.pack_id}@{request.version} "
                f"on queue item {queue_item_id}."
            ),
            execution_path="durable_runtime_worker_execution",
            related_evaluation_run_id=None,
            latest_message="Workflow-pack execution accepted into durable async runtime state.",
            attempt_count=1,
            artifact_ids=[snapshot_ref.artifact_id],
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
            recorded_message="Initial workflow-pack async execution submission recorded.",
        )
        store = get_async_runtime_store()
        store.save_job(job_record)
        store.save_attempt(attempt_record)
        delivery_published = publish_async_attempt_if_configured(
            job=job_record,
            attempt=attempt_record,
        )
        return WorkflowPackAsyncExecutionSubmissionResponse(
            service=settings.service_name,
            version=settings.service_version,
            phase=settings.delivery_phase,
            accepted=True,
            idempotency_key=idempotency_key,
            idempotency_status="CREATED",
            queue_item_id=queue_item_id,
            async_job=map_async_runtime_job(job_record),
            queue_event=queued_event,
            status_summary=[
                "Workflow-pack execution was persisted as a durable async runtime job.",
                "The retained queue request snapshot is the executable worker input; raw task payloads are not embedded in queue events.",
                (
                    "The async attempt was published to the managed delivery queue."
                    if delivery_published
                    else "The async job is durable; managed queue publication is inactive under the current async cutover posture."
                ),
            ],
        )


def run_next_workflow_pack_execution_job(
    *,
    worker_id: str,
) -> WorkflowPackAsyncExecutionResult | None:
    claim = claim_next_async_job_for_types(
        worker_id=worker_id,
        job_types=(WORKFLOW_PACK_EXECUTION_ASYNC_JOB_TYPE,),
    )
    if claim is None:
        return None
    return _execute_claimed_workflow_pack_job(claim=claim, worker_id=worker_id)


def run_workflow_pack_execution_job_by_id(
    *,
    async_job_id: str,
    worker_id: str,
) -> WorkflowPackAsyncExecutionResult | None:
    claim = claim_async_job_by_id(job_id=async_job_id, worker_id=worker_id)
    if claim is None:
        return None
    return _execute_claimed_workflow_pack_job(claim=claim, worker_id=worker_id)


@dataclass(frozen=True)
class _ResolvedWorkflowPackAsyncSubmission:
    registration: WorkflowPackRegistrationDescriptor
    policy: WorkflowPackQueuePolicyDescriptor
    workflow_surface: str


def _preflight_workflow_pack_execution_request(
    *,
    request: WorkflowPackExecutionRequest,
) -> _ResolvedWorkflowPackAsyncSubmission:
    resolved_binding = get_resolved_workflow_pack_execution_binding(
        pack_id=request.pack_id,
        version=request.version,
    )
    if resolved_binding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown workflow-pack registration: {request.pack_id}@{request.version}",
        )
    workflow_surface = request.workflow_surface or resolved_binding.binding.default_workflow_surface
    enforce_kill_switch_intake(
        task_id=request.task_request.task_id,
        tenant_id=request.task_request.caller.tenant_id,
        caller_app=request.task_request.caller.caller_app,
    )
    eligibility = evaluate_workflow_pack_eligibility(
        WorkflowPackEligibilityEvaluationRequest(
            pack_id=request.pack_id,
            version=request.version,
            caller_app=request.task_request.caller.caller_app,
            environment=request.environment,
            caller_identity_class=request.caller_identity_class,
            tenant_id=request.task_request.caller.tenant_id,
            workflow_surface=workflow_surface,
        )
    )
    if not eligibility.allowed:
        detail = (
            eligibility.denial_reasons[0]
            if eligibility.denial_reasons
            else "Workflow-pack execution is not currently allowed."
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
    validate_workflow_pack_execution_binding(
        request=request,
        binding=resolved_binding.binding,
    )
    validate_task_request(request.task_request)
    ensure_workflow_pack_run_store_ready()
    ensure_workflow_pack_task_flow_store_ready()
    _ensure_queue_event_store_ready_for_async_submission()
    policy = get_workflow_pack_queue_policy_descriptor(
        pack_id=request.pack_id,
        version=request.version,
    )
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Workflow-pack queue policy is not declared for executable version "
                f"`{request.pack_id}@{request.version}`."
            ),
        )
    return _ResolvedWorkflowPackAsyncSubmission(
        registration=resolved_binding.registration,
        policy=policy,
        workflow_surface=workflow_surface,
    )


def _ensure_queue_event_store_ready_for_async_submission() -> None:
    try:
        ensure_workflow_pack_queue_event_store_ready()
    except WorkflowPackQueueEventStoreNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


def _resolve_existing_idempotent_async_submission(
    *,
    request: WorkflowPackExecutionRequest,
    policy: WorkflowPackQueuePolicyDescriptor,
    workflow_surface: str,
    request_fingerprint: str,
    idempotency_key: str,
) -> WorkflowPackAsyncExecutionSubmissionResponse | None:
    for job in get_async_runtime_store().list_jobs():
        if (
            job.job_type != WORKFLOW_PACK_EXECUTION_ASYNC_JOB_TYPE
            or job.caller_app != request.task_request.caller.caller_app
        ):
            continue
        snapshot = _load_first_snapshot_for_job(job=job)
        if snapshot is None:
            continue
        if snapshot.get("pack_id") != policy.workflow_pack_id:
            continue
        if snapshot.get("pack_version") != policy.workflow_pack_version:
            continue
        existing_idempotency_key = _resolve_snapshot_idempotency_key(payload=snapshot)
        if existing_idempotency_key != idempotency_key:
            continue
        existing_fingerprint = _fingerprint_async_snapshot_payload(payload=snapshot)
        if existing_fingerprint != request_fingerprint:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Workflow-pack async idempotency conflict: idempotency key "
                    f"`{idempotency_key}` was reused with different execution input for "
                    f"`{policy.workflow_pack_id}@{policy.workflow_pack_version}`."
                ),
            )
        queue_event = _load_queued_event_for_existing_submission(job=job)
        return WorkflowPackAsyncExecutionSubmissionResponse(
            service=settings.service_name,
            version=settings.service_version,
            phase=settings.delivery_phase,
            accepted=True,
            idempotency_key=idempotency_key,
            idempotency_status="REPLAYED",
            queue_item_id=queue_event.queue_item_id,
            async_job=map_async_runtime_job(job),
            queue_event=queue_event,
            status_summary=[
                "Workflow-pack async submission reused an existing durable async runtime job for the same idempotent command.",
                (
                    "The retained queue request snapshot matched the current request fingerprint; "
                    "no duplicate queue event, async job, attempt, or managed queue delivery was created."
                ),
                f"The existing async job is currently `{job.lifecycle_status}`.",
            ],
        )
    return None


def _load_queued_event_for_existing_submission(
    *,
    job: AsyncRuntimeJobRecord,
) -> WorkflowPackQueueEventDescriptor:
    if job.target_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Existing workflow-pack async job `{job.job_id}` does not include a queue item."
            ),
        )
    detail = build_workflow_pack_queue_event_detail(queue_item_id=job.target_id)
    queued_events = [
        event
        for event in detail.events
        if event.event_type is WorkflowPackQueueEventType.ADMISSION_QUEUED
    ]
    if not queued_events:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Existing workflow-pack async job `{job.job_id}` is missing queued event truth."
            ),
        )
    return queued_events[-1]


def _build_async_submission_idempotency_key(*, request: WorkflowPackExecutionRequest) -> str:
    explicit_key = _normalize_idempotency_key(request.idempotency_key)
    if explicit_key is not None:
        return explicit_key
    source = _canonical_json(
        {
            "operation": "workflow-pack-execute-async",
            "caller_app": request.task_request.caller.caller_app,
            "pack_id": request.pack_id,
            "version": request.version,
            "correlation_id": request.task_request.caller.correlation_id,
        }
    )
    return "wp_async_" + hashlib.sha256(source).hexdigest()[:32]


def _resolve_snapshot_idempotency_key(*, payload: dict[str, object]) -> str | None:
    existing_key = payload.get("idempotency_key")
    if isinstance(existing_key, str) and existing_key.strip():
        return existing_key.strip()
    task_request = payload.get("task_request")
    if not isinstance(task_request, dict):
        return None
    caller = task_request.get("caller")
    if not isinstance(caller, dict):
        return None
    source = _canonical_json(
        {
            "operation": "workflow-pack-execute-async",
            "caller_app": caller.get("caller_app"),
            "pack_id": payload.get("pack_id"),
            "version": payload.get("pack_version"),
            "correlation_id": caller.get("correlation_id"),
        }
    )
    return "wp_async_" + hashlib.sha256(source).hexdigest()[:32]


def _normalize_idempotency_key(idempotency_key: str | None) -> str | None:
    if idempotency_key is None:
        return None
    normalized = idempotency_key.strip()
    return normalized or None


def _fingerprint_async_execution_request(
    *,
    request: WorkflowPackExecutionRequest,
    lane: WorkflowPackQueueLane,
    workflow_surface: str,
) -> str:
    payload = {
        "pack_id": request.pack_id,
        "pack_version": request.version,
        "workflow_surface": workflow_surface,
        "environment": request.environment.value,
        "caller_identity_class": request.caller_identity_class.value,
        "queue_lane": lane.value,
        "task_request": request.task_request.model_dump(mode="json"),
    }
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _fingerprint_async_snapshot_payload(*, payload: dict[str, object]) -> str:
    normalized = {
        "pack_id": payload.get("pack_id"),
        "pack_version": payload.get("pack_version"),
        "workflow_surface": payload.get("workflow_surface"),
        "environment": payload.get("environment"),
        "caller_identity_class": payload.get("caller_identity_class"),
        "queue_lane": payload.get("queue_lane"),
        "task_request": payload.get("task_request"),
    }
    return hashlib.sha256(_canonical_json(normalized)).hexdigest()


def _canonical_json(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode(
        "ascii"
    )


def _execute_claimed_workflow_pack_job(
    *,
    claim: AsyncWorkerClaimResult,
    worker_id: str,
) -> WorkflowPackAsyncExecutionResult | None:
    with drain_completion_permit():
        return _execute_claimed_workflow_pack_job_inner(claim=claim, worker_id=worker_id)


def _execute_claimed_workflow_pack_job_inner(
    *,
    claim: AsyncWorkerClaimResult,
    worker_id: str,
) -> WorkflowPackAsyncExecutionResult | None:
    if claim.job.job_type != WORKFLOW_PACK_EXECUTION_ASYNC_JOB_TYPE or claim.job.target_id is None:
        fail_async_job(
            job_id=claim.job.job_id,
            worker_id=worker_id,
            failure_reason="UNSUPPORTED_ASYNC_JOB_TYPE",
            retryable=False,
        )
        return _failed_result(claim=claim, queue_item_id=claim.job.target_id)
    try:
        source_event = _load_queued_source_event(queue_item_id=claim.job.target_id)
    except Exception as exc:
        fail_async_job(
            job_id=claim.job.job_id,
            worker_id=worker_id,
            failure_reason=type(exc).__name__,
            retryable=False,
        )
        return _failed_result(claim=claim, queue_item_id=claim.job.target_id)
    try:
        execution_request = build_workflow_pack_execution_request_from_queue_snapshot(
            source_event=source_event,
        )
    except Exception as exc:
        _fail_claimed_workflow_pack_job(
            claim=claim,
            worker_id=worker_id,
            source_event=source_event,
            failure_reason=type(exc).__name__,
        )
        return _failed_result(claim=claim, queue_item_id=source_event.queue_item_id)
    policy = get_workflow_pack_queue_policy_descriptor(
        pack_id=execution_request.pack_id,
        version=execution_request.version,
    )
    if policy is None:
        _fail_claimed_workflow_pack_job(
            claim=claim,
            worker_id=worker_id,
            source_event=source_event,
            failure_reason="QUEUE_POLICY_NOT_FOUND",
        )
        return _failed_result(claim=claim, queue_item_id=source_event.queue_item_id)
    admitted_state = _transition(
        current_state=source_event.state,
        next_state=WorkflowPackQueueState.ADMITTED,
    )
    _record_queue_event(
        queue_item_id=source_event.queue_item_id,
        event_type=WorkflowPackQueueEventType.ADMISSION_ADMITTED,
        policy=policy,
        lane=source_event.lane or policy.default_lane,
        state=admitted_state,
        request=execution_request,
        workflow_surface=source_event.workflow_surface,
        artifact_refs=source_event.artifact_refs,
        message="Workflow-pack queued worker job admitted for dedicated execution.",
    )
    running_state = _transition(
        current_state=admitted_state,
        next_state=WorkflowPackQueueState.RUNNING,
    )
    _record_queue_event(
        queue_item_id=source_event.queue_item_id,
        event_type=WorkflowPackQueueEventType.ADMISSION_GRANTED,
        policy=policy,
        lane=source_event.lane or policy.default_lane,
        state=running_state,
        request=execution_request,
        workflow_surface=source_event.workflow_surface,
        artifact_refs=source_event.artifact_refs,
        message="Workflow-pack queued worker job handed to the governed execution seam.",
    )
    try:
        start_async_job(job_id=claim.job.job_id, worker_id=worker_id)
        execution = execute_workflow_pack(execution_request)
    except Exception as exc:
        _fail_claimed_workflow_pack_job(
            claim=claim,
            worker_id=worker_id,
            source_event=source_event,
            failure_reason=type(exc).__name__,
        )
        if isinstance(exc, HTTPException):
            return _failed_result(claim=claim, queue_item_id=source_event.queue_item_id)
        raise

    _record_queue_event(
        queue_item_id=source_event.queue_item_id,
        event_type=WorkflowPackQueueEventType.ADMISSION_RELEASED,
        policy=policy,
        lane=source_event.lane or policy.default_lane,
        state=_transition(
            current_state=running_state,
            next_state=WorkflowPackQueueState.COMPLETED_HANDOFF,
        ),
        request=execution_request,
        workflow_surface=source_event.workflow_surface,
        artifact_refs=source_event.artifact_refs,
        message=(
            "Workflow-pack queued worker job completed execution handoff and produced run "
            f"`{execution.workflow_pack_run.run_id}`."
        ),
    )
    complete_async_job(
        job_id=claim.job.job_id,
        worker_id=worker_id,
        message=(
            "Workflow-pack queued worker execution completed and produced run "
            f"`{execution.workflow_pack_run.run_id}`."
        ),
    )
    return WorkflowPackAsyncExecutionResult(
        async_job_id=claim.job.job_id,
        queue_item_id=source_event.queue_item_id,
        workflow_pack_run_id=execution.workflow_pack_run.run_id,
        terminal_status=AsyncJobStatus.COMPLETED.value,
    )


def _failed_result(
    *,
    claim: AsyncWorkerClaimResult,
    queue_item_id: str | None,
) -> WorkflowPackAsyncExecutionResult:
    return WorkflowPackAsyncExecutionResult(
        async_job_id=claim.job.job_id,
        queue_item_id=queue_item_id or "",
        workflow_pack_run_id=None,
        terminal_status=AsyncJobStatus.FAILED.value,
    )


def _fail_claimed_workflow_pack_job(
    *,
    claim: AsyncWorkerClaimResult,
    worker_id: str,
    source_event: WorkflowPackQueueEventDescriptor,
    failure_reason: str,
) -> None:
    fail_async_job(
        job_id=claim.job.job_id,
        worker_id=worker_id,
        failure_reason=failure_reason,
        retryable=False,
    )
    _record_queue_event(
        queue_item_id=source_event.queue_item_id,
        event_type=WorkflowPackQueueEventType.ADMISSION_DEGRADED,
        policy_id=source_event.policy_id,
        workflow_pack_id=source_event.workflow_pack_id,
        workflow_pack_version=source_event.workflow_pack_version,
        lane=source_event.lane,
        state=WorkflowPackQueueState.DEGRADED,
        caller_app=source_event.caller_app,
        correlation_id=source_event.correlation_id,
        tenant_id=source_event.tenant_id,
        workflow_surface=source_event.workflow_surface,
        artifact_refs=source_event.artifact_refs,
        reason_code=failure_reason,
        message=(
            "Workflow-pack queued worker execution failed before completed handoff with reason "
            f"`{failure_reason}`."
        ),
    )


def _load_queued_source_event(*, queue_item_id: str) -> WorkflowPackQueueEventDescriptor:
    from app.services.workflow_pack_queue_events import build_workflow_pack_queue_event_detail

    detail = build_workflow_pack_queue_event_detail(queue_item_id=queue_item_id)
    queued_events = [
        event
        for event in detail.events
        if event.event_type is WorkflowPackQueueEventType.ADMISSION_QUEUED
    ]
    if not queued_events:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workflow-pack async job target `{queue_item_id}` is not queued.",
        )
    return queued_events[-1]


def _enforce_queued_capacity(
    *,
    policy: WorkflowPackQueuePolicyDescriptor,
    lane: WorkflowPackQueueLane,
) -> None:
    queued_pack_count = 0
    queued_lane_count = 0
    for job in get_async_runtime_store().list_jobs():
        if (
            job.job_type != WORKFLOW_PACK_EXECUTION_ASYNC_JOB_TYPE
            or job.lifecycle_status not in _ACTIVE_ASYNC_JOB_STATUSES
        ):
            continue
        snapshot = _load_first_snapshot_for_job(job=job)
        if snapshot is None:
            continue
        if snapshot.get("pack_id") != policy.workflow_pack_id:
            continue
        if snapshot.get("pack_version") != policy.workflow_pack_version:
            continue
        queued_pack_count += 1
        if snapshot.get("queue_lane") == lane.value:
            queued_lane_count += 1
    if queued_pack_count >= policy.max_queued_runs_per_pack:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Workflow-pack async queue rejected admission because "
                f"`max_queued_runs_per_pack` is already at {policy.max_queued_runs_per_pack}."
            ),
        )
    if queued_lane_count >= policy.max_queued_runs_per_lane:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Workflow-pack async queue rejected admission because "
                f"`max_queued_runs_per_lane` is already at {policy.max_queued_runs_per_lane}."
            ),
        )


def _reject_duplicate_active_submission(
    *,
    request: WorkflowPackExecutionRequest,
    policy: WorkflowPackQueuePolicyDescriptor,
) -> None:
    for job in get_async_runtime_store().list_jobs():
        if (
            job.job_type != WORKFLOW_PACK_EXECUTION_ASYNC_JOB_TYPE
            or job.lifecycle_status not in _ACTIVE_ASYNC_JOB_STATUSES
            or job.caller_app != request.task_request.caller.caller_app
            or job.correlation_id != request.task_request.caller.correlation_id
        ):
            continue
        snapshot = _load_first_snapshot_for_job(job=job)
        if snapshot is None:
            continue
        if snapshot.get("pack_id") != policy.workflow_pack_id:
            continue
        if snapshot.get("pack_version") != policy.workflow_pack_version:
            continue
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Duplicate workflow-pack async execution rejected because active async job "
                f"`{job.job_id}` already owns correlation id "
                f"`{request.task_request.caller.correlation_id}` for "
                f"`{policy.workflow_pack_id}@{policy.workflow_pack_version}`."
            ),
        )


def _load_first_snapshot_for_job(*, job: AsyncRuntimeJobRecord) -> dict[str, object] | None:
    for artifact in load_artifact_descriptors(artifact_ids=job.artifact_ids):
        if artifact.artifact_type != QUEUE_REQUEST_SNAPSHOT_ARTIFACT_TYPE:
            continue
        return load_workflow_pack_queue_request_snapshot_payload(snapshot_ref=artifact)
    return None


def _validate_lane(
    *,
    policy: WorkflowPackQueuePolicyDescriptor,
    lane: WorkflowPackQueueLane,
) -> None:
    if lane in set(policy.allowed_lanes):
        return
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"Workflow-pack queue lane `{lane.value}` is not allowed for "
            f"`{policy.workflow_pack_id}@{policy.workflow_pack_version}`."
        ),
    )


def _transition(
    *,
    current_state: WorkflowPackQueueState,
    next_state: WorkflowPackQueueState,
) -> WorkflowPackQueueState:
    if not is_workflow_pack_queue_state_transition_allowed(
        current_state=current_state,
        next_state=next_state,
    ):
        raise RuntimeError(
            f"Illegal workflow-pack queue transition: {current_state.value} -> {next_state.value}"
        )
    return next_state


def _record_queue_event(
    *,
    queue_item_id: str,
    event_type: WorkflowPackQueueEventType,
    state: WorkflowPackQueueState,
    message: str,
    request: WorkflowPackExecutionRequest | None = None,
    workflow_surface: str | None = None,
    policy: WorkflowPackQueuePolicyDescriptor | None = None,
    policy_id: str | None = None,
    workflow_pack_id: str | None = None,
    workflow_pack_version: str | None = None,
    lane: WorkflowPackQueueLane | None = None,
    caller_app: str | None = None,
    correlation_id: str | None = None,
    tenant_id: str | None = None,
    artifact_refs: list[ArtifactDescriptor] | None = None,
    reason_code: str | None = None,
    idempotency_key: str | None = None,
    idempotency_request_fingerprint: str | None = None,
) -> WorkflowPackQueueEventDescriptor:
    resolved_workflow_pack_id = (
        policy.workflow_pack_id
        if policy is not None
        else workflow_pack_id
        if workflow_pack_id is not None
        else request.pack_id
        if request is not None
        else None
    )
    resolved_workflow_pack_version = (
        policy.workflow_pack_version
        if policy is not None
        else workflow_pack_version
        if workflow_pack_version is not None
        else request.version
        if request is not None
        else None
    )
    if resolved_workflow_pack_id is None or resolved_workflow_pack_version is None:
        raise RuntimeError("Workflow-pack queue event identity is required.")
    return record_workflow_pack_queue_event(
        queue_item_id=queue_item_id,
        event_type=event_type,
        policy_id=policy.policy_id if policy is not None else policy_id,
        workflow_pack_id=resolved_workflow_pack_id,
        workflow_pack_version=resolved_workflow_pack_version,
        lane=lane,
        state=state,
        caller_app=(request.task_request.caller.caller_app if request is not None else caller_app),
        correlation_id=(
            request.task_request.caller.correlation_id if request is not None else correlation_id
        ),
        tenant_id=request.task_request.caller.tenant_id if request is not None else tenant_id,
        workflow_surface=workflow_surface,
        reason_code=reason_code,
        idempotency_key=idempotency_key,
        idempotency_request_fingerprint=idempotency_request_fingerprint,
        artifact_refs=artifact_refs or [],
        message=message,
    )


def _utc_now_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
