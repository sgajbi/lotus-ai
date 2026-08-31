from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Iterator, NoReturn
from uuid import uuid4

from fastapi import HTTPException, status

from app.contracts.artifacts import ArtifactDescriptor
from app.contracts.tasks import TaskExecutionRequest
from app.contracts.workflow_pack_queue_policies import (
    WorkflowPackQueueCancellationActor,
    WorkflowPackQueueEventType,
    WorkflowPackQueueLane,
    WorkflowPackQueuePolicyDescriptor,
    WorkflowPackQueueState,
    is_workflow_pack_queue_state_transition_allowed,
)
from app.contracts.workflow_packs import (
    WorkflowPackCallerIdentityClass,
    WorkflowPackEnvironment,
    WorkflowPackRegistrationDescriptor,
)
from app.services.workflow_pack_queue_events import (
    WorkflowPackQueueEventStoreNotReadyError,
    ensure_workflow_pack_queue_event_store_ready,
    record_workflow_pack_queue_event,
)
from app.services.workflow_pack_queue_policy_catalog import (
    get_workflow_pack_queue_policy_descriptor,
)
from app.services.workflow_pack_queue_request_snapshots import (
    persist_workflow_pack_queue_request_snapshot,
)


from app.services.workflow_pack_admission_lease_store import (
    get_workflow_pack_admission_lease_repository,
)
from app.services.workflow_pack_queue_admission_models import (
    WorkflowPackQueueAdmissionLease,
)

_queue_lock = RLock()


@contextmanager
def workflow_pack_queue_admission(
    *,
    registration: WorkflowPackRegistrationDescriptor,
    requested_lane: WorkflowPackQueueLane | None = None,
    caller_app: str | None = None,
    correlation_id: str | None = None,
    tenant_id: str | None = None,
    workflow_surface: str | None = None,
    task_request: TaskExecutionRequest | None = None,
    environment: WorkflowPackEnvironment | None = None,
    caller_identity_class: WorkflowPackCallerIdentityClass | None = None,
) -> Iterator[WorkflowPackQueueAdmissionLease]:
    lease = acquire_workflow_pack_queue_admission(
        registration=registration,
        requested_lane=requested_lane,
        caller_app=caller_app,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        workflow_surface=workflow_surface,
        task_request=task_request,
        environment=environment,
        caller_identity_class=caller_identity_class,
    )
    try:
        yield lease
    finally:
        release_workflow_pack_queue_admission(lease.queue_item_id)


def acquire_workflow_pack_queue_admission(
    *,
    registration: WorkflowPackRegistrationDescriptor,
    requested_lane: WorkflowPackQueueLane | None = None,
    caller_app: str | None = None,
    correlation_id: str | None = None,
    tenant_id: str | None = None,
    workflow_surface: str | None = None,
    task_request: TaskExecutionRequest | None = None,
    environment: WorkflowPackEnvironment | None = None,
    caller_identity_class: WorkflowPackCallerIdentityClass | None = None,
) -> WorkflowPackQueueAdmissionLease:
    _ensure_queue_event_store_ready_for_admission()
    queue_item_id = f"wpq_{uuid4().hex}"
    policy = get_workflow_pack_queue_policy_descriptor(
        pack_id=registration.pack_id,
        version=registration.version,
    )
    if policy is None:
        _record_queue_event(
            queue_item_id=queue_item_id,
            event_type=WorkflowPackQueueEventType.ADMISSION_REJECTED,
            workflow_pack_id=registration.pack_id,
            workflow_pack_version=registration.version,
            state=WorkflowPackQueueState.REJECTED,
            lane=requested_lane,
            caller_app=caller_app,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            workflow_surface=workflow_surface,
            reason_code="QUEUE_POLICY_NOT_FOUND",
            message=(
                "Workflow-pack queue admission rejected because no queue policy is "
                f"declared for `{registration.pack_id}@{registration.version}`."
            ),
        )
        _raise_queue_rejection(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Workflow-pack queue policy is not declared for executable version "
                f"`{registration.pack_id}@{registration.version}`."
            ),
        )

    lane = requested_lane or policy.default_lane
    request_artifact_refs = _persist_request_snapshot_artifact_refs(
        queue_item_id=queue_item_id,
        registration=registration,
        lane=lane,
        task_request=task_request,
        workflow_surface=workflow_surface,
        environment=environment,
        caller_identity_class=caller_identity_class,
    )
    _record_queue_event(
        queue_item_id=queue_item_id,
        event_type=WorkflowPackQueueEventType.ADMISSION_REQUESTED,
        policy=policy,
        lane=lane,
        state=WorkflowPackQueueState.NOT_ADMITTED,
        caller_app=caller_app,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        workflow_surface=workflow_surface,
        artifact_refs=request_artifact_refs,
        message=(
            "Workflow-pack queue admission requested for "
            f"`{policy.workflow_pack_id}@{policy.workflow_pack_version}` in lane `{lane.value}`."
        ),
    )
    if lane not in set(policy.allowed_lanes):
        _record_queue_event(
            queue_item_id=queue_item_id,
            event_type=WorkflowPackQueueEventType.ADMISSION_REJECTED,
            policy=policy,
            lane=lane,
            state=WorkflowPackQueueState.REJECTED,
            caller_app=caller_app,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            workflow_surface=workflow_surface,
            artifact_refs=request_artifact_refs,
            reason_code="QUEUE_LANE_NOT_ALLOWED",
            message=(
                "Workflow-pack queue admission rejected because the requested lane "
                f"`{lane.value}` is not allowed."
            ),
        )
        _raise_queue_rejection(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Workflow-pack queue lane `{lane.value}` is not allowed for "
                f"`{registration.pack_id}@{registration.version}`."
            ),
        )

    with _queue_lock:
        active_pack_count = _count_active_leases(policy=policy)
        active_lane_count = _count_active_leases(policy=policy, lane=lane)
        if active_pack_count >= policy.max_concurrent_runs_per_pack:
            _raise_capacity_rejection(
                queue_item_id=queue_item_id,
                policy=policy,
                lane=lane,
                limit_name="max_concurrent_runs_per_pack",
                limit=policy.max_concurrent_runs_per_pack,
                caller_app=caller_app,
                correlation_id=correlation_id,
                tenant_id=tenant_id,
                workflow_surface=workflow_surface,
                artifact_refs=request_artifact_refs,
            )
        if active_lane_count >= policy.max_concurrent_runs_per_lane:
            _raise_capacity_rejection(
                queue_item_id=queue_item_id,
                policy=policy,
                lane=lane,
                limit_name="max_concurrent_runs_per_lane",
                limit=policy.max_concurrent_runs_per_lane,
                caller_app=caller_app,
                correlation_id=correlation_id,
                tenant_id=tenant_id,
                workflow_surface=workflow_surface,
                artifact_refs=request_artifact_refs,
            )

        queued_state = _transition_queue_state(
            current_state=WorkflowPackQueueState.NOT_ADMITTED,
            next_state=WorkflowPackQueueState.QUEUED,
        )
        _record_admission_lifecycle_event(
            queue_item_id=queue_item_id,
            event_type=WorkflowPackQueueEventType.ADMISSION_QUEUED,
            policy=policy,
            lane=lane,
            state=queued_state,
            caller_app=caller_app,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            workflow_surface=workflow_surface,
            artifact_refs=request_artifact_refs,
            message=(
                "Workflow-pack queue item queued after policy and capacity evaluation for "
                f"`{policy.workflow_pack_id}@{policy.workflow_pack_version}` in lane "
                f"`{lane.value}`."
            ),
        )
        admitted_state = _transition_queue_state(
            current_state=queued_state,
            next_state=WorkflowPackQueueState.ADMITTED,
        )
        _record_admission_lifecycle_event(
            queue_item_id=queue_item_id,
            event_type=WorkflowPackQueueEventType.ADMISSION_ADMITTED,
            policy=policy,
            lane=lane,
            state=admitted_state,
            caller_app=caller_app,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            workflow_surface=workflow_surface,
            artifact_refs=request_artifact_refs,
            message=(
                "Workflow-pack queue item admitted for execution handoff for "
                f"`{policy.workflow_pack_id}@{policy.workflow_pack_version}` in lane "
                f"`{lane.value}`."
            ),
        )
        running_state = _transition_queue_state(
            current_state=admitted_state,
            next_state=WorkflowPackQueueState.RUNNING,
        )
        lease = WorkflowPackQueueAdmissionLease(
            queue_item_id=queue_item_id,
            policy_id=policy.policy_id,
            workflow_pack_id=policy.workflow_pack_id,
            workflow_pack_version=policy.workflow_pack_version,
            lane=lane,
            state=running_state,
            admitted_at=_utc_now_timestamp(),
            caller_app=caller_app,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            workflow_surface=workflow_surface,
            artifact_refs=tuple(request_artifact_refs),
        )
        attempt = get_workflow_pack_admission_lease_repository().try_admit(
            lease,
            pack_limit=policy.max_concurrent_runs_per_pack,
            lane_limit=policy.max_concurrent_runs_per_lane,
        )
        _record_reclaimed_lease_events(attempt.reclaimed_leases)
        if not attempt.admitted:
            # The repository is the authoritative, replica-atomic capacity
            # decision; the earlier check is an advisory fast-fail. Losing
            # the race here is a plain capacity rejection.
            limit_name = (
                "max_concurrent_runs_per_pack"
                if attempt.active_pack_count >= policy.max_concurrent_runs_per_pack
                else "max_concurrent_runs_per_lane"
            )
            _raise_capacity_rejection(
                queue_item_id=queue_item_id,
                policy=policy,
                lane=lane,
                limit_name=limit_name,
                limit=getattr(policy, limit_name),
                caller_app=caller_app,
                correlation_id=correlation_id,
                tenant_id=tenant_id,
                workflow_surface=workflow_surface,
                artifact_refs=request_artifact_refs,
            )

        # The grant is recorded only after the authoritative, replica-atomic
        # admit succeeds: recording it first made a lost race read
        # granted-then-rejected for one queue item in the durable history,
        # in exactly the race the leases exist for (issue #228).
        _record_queue_event(
            queue_item_id=lease.queue_item_id,
            event_type=WorkflowPackQueueEventType.ADMISSION_GRANTED,
            policy=policy,
            lane=lane,
            state=running_state,
            caller_app=caller_app,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            workflow_surface=workflow_surface,
            artifact_refs=request_artifact_refs,
            message=(
                "Workflow-pack queue admission granted for "
                f"`{policy.workflow_pack_id}@{policy.workflow_pack_version}` in lane `{lane.value}`."
            ),
        )
        return lease


def release_workflow_pack_queue_admission(
    queue_item_id: str,
    *,
    now_utc: datetime | None = None,
) -> None:
    lease = get_workflow_pack_admission_lease_repository().get_lease(queue_item_id)
    if lease is None:
        return
    policy = _get_policy_for_lease(lease)
    terminal_state = _release_terminal_state(lease=lease, policy=policy, now_utc=now_utc)
    event_type = (
        WorkflowPackQueueEventType.ADMISSION_TIMED_OUT
        if terminal_state is WorkflowPackQueueState.TIMED_OUT
        else WorkflowPackQueueEventType.ADMISSION_RELEASED
    )
    release_state = _transition_queue_state(
        current_state=lease.state,
        next_state=terminal_state,
    )
    if not get_workflow_pack_admission_lease_repository().delete_lease(queue_item_id):
        # Another replica already claimed this terminal transition; recording a
        # second event would duplicate the queue item's terminal history.
        return

    _record_queue_event(
        queue_item_id=lease.queue_item_id,
        event_type=event_type,
        workflow_pack_id=lease.workflow_pack_id,
        workflow_pack_version=lease.workflow_pack_version,
        policy_id=lease.policy_id,
        lane=lease.lane,
        state=release_state,
        caller_app=lease.caller_app,
        correlation_id=lease.correlation_id,
        tenant_id=lease.tenant_id,
        workflow_surface=lease.workflow_surface,
        artifact_refs=lease.artifact_refs,
        reason_code=(
            "EXECUTION_TIMEOUT"
            if event_type is WorkflowPackQueueEventType.ADMISSION_TIMED_OUT
            else None
        ),
        message=_release_event_message(lease=lease, event_type=event_type, policy=policy),
    )


def cancel_workflow_pack_queue_admission(
    queue_item_id: str,
    *,
    actor: WorkflowPackQueueCancellationActor,
    reason: str,
    evidence_ref: str,
) -> bool:
    if not reason.strip() or not evidence_ref.strip():
        _raise_queue_rejection(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Workflow-pack queue cancellation requires non-empty reason and evidence_ref.",
        )
    lease = get_workflow_pack_admission_lease_repository().get_lease(queue_item_id)
    if lease is None:
        return False
    policy = _get_policy_for_lease(lease)
    if actor not in set(policy.cancellation_policy.cancellable_by):
        _raise_queue_rejection(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Workflow-pack queue admission `{queue_item_id}` cannot be cancelled by "
                f"`{actor.value}` under policy `{policy.policy_id}`."
            ),
        )
    cancellation_state = _transition_queue_state(
        current_state=lease.state,
        next_state=WorkflowPackQueueState.CANCELLED,
    )
    if not get_workflow_pack_admission_lease_repository().delete_lease(queue_item_id):
        # Another replica already claimed this terminal transition (issue #228).
        return False

    _record_queue_event(
        queue_item_id=lease.queue_item_id,
        event_type=WorkflowPackQueueEventType.ADMISSION_CANCELLED,
        workflow_pack_id=lease.workflow_pack_id,
        workflow_pack_version=lease.workflow_pack_version,
        policy_id=lease.policy_id,
        lane=lease.lane,
        state=cancellation_state,
        caller_app=lease.caller_app,
        correlation_id=lease.correlation_id,
        tenant_id=lease.tenant_id,
        workflow_surface=lease.workflow_surface,
        artifact_refs=lease.artifact_refs,
        reason_code="QUEUE_ADMISSION_CANCELLED",
        message=(
            "Workflow-pack queue admission cancelled by "
            f"`{actor.value}` with evidence `{evidence_ref}`: {reason}"
        ),
    )
    return True


def list_active_workflow_pack_queue_admissions() -> list[WorkflowPackQueueAdmissionLease]:
    return get_workflow_pack_admission_lease_repository().list_leases()


def get_active_workflow_pack_queue_admission(
    queue_item_id: str,
) -> WorkflowPackQueueAdmissionLease | None:
    return get_workflow_pack_admission_lease_repository().get_lease(queue_item_id)


def reset_workflow_pack_queue_admission_state() -> None:
    get_workflow_pack_admission_lease_repository().clear()


def _count_active_leases(
    *,
    policy: WorkflowPackQueuePolicyDescriptor,
    lane: WorkflowPackQueueLane | None = None,
) -> int:
    return sum(
        1
        for lease in get_workflow_pack_admission_lease_repository().list_leases()
        if lease.policy_id == policy.policy_id and (lane is None or lease.lane is lane)
    )


def _transition_queue_state(
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


def _raise_capacity_rejection(
    *,
    queue_item_id: str,
    policy: WorkflowPackQueuePolicyDescriptor,
    lane: WorkflowPackQueueLane,
    limit_name: str,
    limit: int,
    caller_app: str | None = None,
    correlation_id: str | None = None,
    tenant_id: str | None = None,
    workflow_surface: str | None = None,
    artifact_refs: list[ArtifactDescriptor] | None = None,
) -> None:
    _record_queue_event(
        queue_item_id=queue_item_id,
        event_type=WorkflowPackQueueEventType.ADMISSION_REJECTED,
        policy=policy,
        lane=lane,
        state=WorkflowPackQueueState.REJECTED,
        caller_app=caller_app,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        workflow_surface=workflow_surface,
        artifact_refs=artifact_refs,
        reason_code=limit_name.upper(),
        message=(
            f"Workflow-pack queue admission rejected because `{limit_name}` is already at {limit}."
        ),
    )
    _raise_queue_rejection(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=(
            "Workflow-pack queue policy rejected admission for "
            f"`{policy.workflow_pack_id}@{policy.workflow_pack_version}` in lane "
            f"`{lane.value}` because `{limit_name}` is already at {limit}."
        ),
    )


def _raise_queue_rejection(*, status_code: int, detail: str) -> NoReturn:
    raise HTTPException(status_code=status_code, detail=detail)


def _record_admission_lifecycle_event(
    *,
    queue_item_id: str,
    event_type: WorkflowPackQueueEventType,
    policy: WorkflowPackQueuePolicyDescriptor,
    lane: WorkflowPackQueueLane,
    state: WorkflowPackQueueState,
    message: str,
    caller_app: str | None = None,
    correlation_id: str | None = None,
    tenant_id: str | None = None,
    workflow_surface: str | None = None,
    artifact_refs: list[ArtifactDescriptor] | None = None,
) -> None:
    _record_queue_event(
        queue_item_id=queue_item_id,
        event_type=event_type,
        policy=policy,
        lane=lane,
        state=state,
        caller_app=caller_app,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        workflow_surface=workflow_surface,
        artifact_refs=artifact_refs,
        message=message,
    )


def _persist_request_snapshot_artifact_refs(
    *,
    queue_item_id: str,
    registration: WorkflowPackRegistrationDescriptor,
    lane: WorkflowPackQueueLane,
    task_request: TaskExecutionRequest | None,
    workflow_surface: str | None,
    environment: WorkflowPackEnvironment | None,
    caller_identity_class: WorkflowPackCallerIdentityClass | None,
) -> list[ArtifactDescriptor]:
    if task_request is None:
        return []
    return [
        persist_workflow_pack_queue_request_snapshot(
            queue_item_id=queue_item_id,
            registration=registration,
            lane=lane,
            task_request=task_request,
            workflow_surface=workflow_surface,
            environment=environment,
            caller_identity_class=caller_identity_class,
            created_at=_utc_now_timestamp(),
        )
    ]


def _get_policy_for_lease(
    lease: WorkflowPackQueueAdmissionLease,
) -> WorkflowPackQueuePolicyDescriptor:
    policy = get_workflow_pack_queue_policy_descriptor(
        pack_id=lease.workflow_pack_id,
        version=lease.workflow_pack_version,
    )
    if policy is None:
        raise RuntimeError(
            "Workflow-pack queue policy disappeared for active lease "
            f"`{lease.workflow_pack_id}@{lease.workflow_pack_version}`."
        )
    return policy


def _release_terminal_state(
    *,
    lease: WorkflowPackQueueAdmissionLease,
    policy: WorkflowPackQueuePolicyDescriptor,
    now_utc: datetime | None = None,
) -> WorkflowPackQueueState:
    admitted_at = datetime.fromisoformat(lease.admitted_at.replace("Z", "+00:00"))
    now = now_utc or datetime.now(UTC)
    if now - admitted_at.astimezone(UTC) > timedelta(seconds=policy.execution_timeout_seconds):
        return WorkflowPackQueueState.TIMED_OUT
    return WorkflowPackQueueState.COMPLETED_HANDOFF


def _release_event_message(
    *,
    lease: WorkflowPackQueueAdmissionLease,
    event_type: WorkflowPackQueueEventType,
    policy: WorkflowPackQueuePolicyDescriptor,
) -> str:
    if event_type is WorkflowPackQueueEventType.ADMISSION_TIMED_OUT:
        return (
            "Workflow-pack queue admission released with timeout posture after exceeding "
            f"the policy execution timeout of {policy.execution_timeout_seconds} seconds for "
            f"`{lease.workflow_pack_id}@{lease.workflow_pack_version}`."
        )
    return (
        "Workflow-pack queue admission released after bounded execution handoff for "
        f"`{lease.workflow_pack_id}@{lease.workflow_pack_version}`."
    )


def _ensure_queue_event_store_ready_for_admission() -> None:
    try:
        ensure_workflow_pack_queue_event_store_ready()
    except WorkflowPackQueueEventStoreNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


def _record_queue_event(
    *,
    queue_item_id: str,
    event_type: WorkflowPackQueueEventType,
    state: WorkflowPackQueueState,
    message: str,
    policy: WorkflowPackQueuePolicyDescriptor | None = None,
    workflow_pack_id: str | None = None,
    workflow_pack_version: str | None = None,
    policy_id: str | None = None,
    lane: WorkflowPackQueueLane | None = None,
    caller_app: str | None = None,
    correlation_id: str | None = None,
    tenant_id: str | None = None,
    workflow_surface: str | None = None,
    reason_code: str | None = None,
    artifact_refs: list[ArtifactDescriptor] | tuple[ArtifactDescriptor, ...] | None = None,
) -> None:
    resolved_workflow_pack_id = policy.workflow_pack_id if policy is not None else workflow_pack_id
    resolved_workflow_pack_version = (
        policy.workflow_pack_version if policy is not None else workflow_pack_version
    )
    if resolved_workflow_pack_id is None or resolved_workflow_pack_version is None:
        raise RuntimeError("Workflow-pack queue event identity is required.")
    record_workflow_pack_queue_event(
        queue_item_id=queue_item_id,
        event_type=event_type,
        policy_id=policy.policy_id if policy is not None else policy_id,
        workflow_pack_id=resolved_workflow_pack_id,
        workflow_pack_version=resolved_workflow_pack_version,
        lane=lane,
        state=state,
        caller_app=caller_app,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        workflow_surface=workflow_surface,
        reason_code=reason_code,
        artifact_refs=list(artifact_refs or []),
        message=message,
    )


def _utc_now_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _record_reclaimed_lease_events(
    reclaimed_leases: tuple[WorkflowPackQueueAdmissionLease, ...],
) -> None:
    """Give every reclaimed lease a terminal event (issue #228).

    Reclamation frees capacity held by a replica that can no longer be
    executing its item. Deleting the lease silently would leave that item's
    durable history ending at ADMISSION_GRANTED forever, so support could
    never tell "still running" from "died and was reclaimed".
    """

    for reclaimed in reclaimed_leases:
        _record_queue_event(
            queue_item_id=reclaimed.queue_item_id,
            event_type=WorkflowPackQueueEventType.ADMISSION_RECLAIMED,
            workflow_pack_id=reclaimed.workflow_pack_id,
            workflow_pack_version=reclaimed.workflow_pack_version,
            policy_id=reclaimed.policy_id,
            lane=reclaimed.lane,
            state=WorkflowPackQueueState.TIMED_OUT,
            caller_app=reclaimed.caller_app,
            correlation_id=reclaimed.correlation_id,
            tenant_id=reclaimed.tenant_id,
            workflow_surface=reclaimed.workflow_surface,
            artifact_refs=reclaimed.artifact_refs,
            reason_code="ADMISSION_LEASE_EXPIRED",
            message=(
                "Workflow-pack admission lease expired and was reclaimed: the holding "
                "replica can no longer be executing this item, so its capacity was "
                "returned to the lane."
            ),
        )
