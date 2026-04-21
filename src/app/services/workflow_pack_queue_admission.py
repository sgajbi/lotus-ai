from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from threading import RLock
from typing import Iterator
from uuid import uuid4

from fastapi import HTTPException, status

from app.contracts.workflow_pack_queue_policies import (
    WorkflowPackQueueLane,
    WorkflowPackQueuePolicyDescriptor,
    WorkflowPackQueueState,
    is_workflow_pack_queue_state_transition_allowed,
)
from app.contracts.workflow_packs import WorkflowPackRegistrationDescriptor
from app.services.workflow_pack_queue_policy_catalog import (
    get_workflow_pack_queue_policy_descriptor,
)


@dataclass(frozen=True)
class WorkflowPackQueueAdmissionLease:
    queue_item_id: str
    policy_id: str
    workflow_pack_id: str
    workflow_pack_version: str
    lane: WorkflowPackQueueLane
    state: WorkflowPackQueueState


_queue_lock = RLock()
_active_leases: dict[str, WorkflowPackQueueAdmissionLease] = {}


@contextmanager
def workflow_pack_queue_admission(
    *,
    registration: WorkflowPackRegistrationDescriptor,
    requested_lane: WorkflowPackQueueLane | None = None,
) -> Iterator[WorkflowPackQueueAdmissionLease]:
    lease = acquire_workflow_pack_queue_admission(
        registration=registration,
        requested_lane=requested_lane,
    )
    try:
        yield lease
    finally:
        release_workflow_pack_queue_admission(lease.queue_item_id)


def acquire_workflow_pack_queue_admission(
    *,
    registration: WorkflowPackRegistrationDescriptor,
    requested_lane: WorkflowPackQueueLane | None = None,
) -> WorkflowPackQueueAdmissionLease:
    policy = get_workflow_pack_queue_policy_descriptor(
        pack_id=registration.pack_id,
        version=registration.version,
    )
    if policy is None:
        _raise_queue_rejection(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Workflow-pack queue policy is not declared for executable version "
                f"`{registration.pack_id}@{registration.version}`."
            ),
        )

    lane = requested_lane or policy.default_lane
    if lane not in set(policy.allowed_lanes):
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
                policy=policy,
                lane=lane,
                limit_name="max_concurrent_runs_per_pack",
                limit=policy.max_concurrent_runs_per_pack,
            )
        if active_lane_count >= policy.max_concurrent_runs_per_lane:
            _raise_capacity_rejection(
                policy=policy,
                lane=lane,
                limit_name="max_concurrent_runs_per_lane",
                limit=policy.max_concurrent_runs_per_lane,
            )

        queued_state = _transition_queue_state(
            current_state=WorkflowPackQueueState.NOT_ADMITTED,
            next_state=WorkflowPackQueueState.QUEUED,
        )
        admitted_state = _transition_queue_state(
            current_state=queued_state,
            next_state=WorkflowPackQueueState.ADMITTED,
        )
        running_state = _transition_queue_state(
            current_state=admitted_state,
            next_state=WorkflowPackQueueState.RUNNING,
        )
        lease = WorkflowPackQueueAdmissionLease(
            queue_item_id=f"wpq_{uuid4().hex}",
            policy_id=policy.policy_id,
            workflow_pack_id=policy.workflow_pack_id,
            workflow_pack_version=policy.workflow_pack_version,
            lane=lane,
            state=running_state,
        )
        _active_leases[lease.queue_item_id] = lease
        return lease


def release_workflow_pack_queue_admission(queue_item_id: str) -> None:
    with _queue_lock:
        _active_leases.pop(queue_item_id, None)


def list_active_workflow_pack_queue_admissions() -> list[WorkflowPackQueueAdmissionLease]:
    with _queue_lock:
        return list(_active_leases.values())


def get_active_workflow_pack_queue_admission(
    queue_item_id: str,
) -> WorkflowPackQueueAdmissionLease | None:
    with _queue_lock:
        return _active_leases.get(queue_item_id)


def reset_workflow_pack_queue_admission_state() -> None:
    with _queue_lock:
        _active_leases.clear()


def _count_active_leases(
    *,
    policy: WorkflowPackQueuePolicyDescriptor,
    lane: WorkflowPackQueueLane | None = None,
) -> int:
    return sum(
        1
        for lease in _active_leases.values()
        if lease.workflow_pack_id == policy.workflow_pack_id
        and lease.workflow_pack_version == policy.workflow_pack_version
        and (lane is None or lease.lane == lane)
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
    policy: WorkflowPackQueuePolicyDescriptor,
    lane: WorkflowPackQueueLane,
    limit_name: str,
    limit: int,
) -> None:
    _raise_queue_rejection(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=(
            "Workflow-pack queue policy rejected admission for "
            f"`{policy.workflow_pack_id}@{policy.workflow_pack_version}` in lane "
            f"`{lane.value}` because `{limit_name}` is already at {limit}."
        ),
    )


def _raise_queue_rejection(*, status_code: int, detail: str) -> None:
    raise HTTPException(status_code=status_code, detail=detail)
