from datetime import datetime, timedelta

from fastapi import HTTPException

from app.contracts.workflow_pack_queue_policies import (
    WorkflowPackQueueCancellationActor,
    WorkflowPackQueueEventDescriptor,
    WorkflowPackQueueLane,
)
from app.contracts.workflow_packs import WorkflowPackRegistrationDescriptor
from app.services.workflow_pack_queue_admission import (
    acquire_workflow_pack_queue_admission,
    cancel_workflow_pack_queue_admission,
    release_workflow_pack_queue_admission,
)
from app.services.workflow_pack_queue_events import (
    build_workflow_pack_queue_event_catalog,
    build_workflow_pack_queue_event_detail,
)
from app.services.workflow_pack_registry import get_workflow_pack_registration


def _advisor_brief_registration() -> WorkflowPackRegistrationDescriptor:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    return registration


def test_queue_admission_acquires_releases_and_records_durable_event_history() -> None:
    lease = acquire_workflow_pack_queue_admission(
        registration=_advisor_brief_registration(),
        caller_app="lotus-gateway",
        correlation_id="corr-queue-admission-1",
        tenant_id="tenant-sg-001",
        workflow_surface="advisor-brief-panel",
    )

    assert lease.policy_id == "queue-policy.advisor-brief.v1"
    assert lease.workflow_pack_id == "advisor_brief.pack"
    assert lease.workflow_pack_version == "v1"
    assert lease.lane == WorkflowPackQueueLane.LATENCY_SENSITIVE
    assert lease.state.value == "RUNNING"

    release_workflow_pack_queue_admission(lease.queue_item_id)
    history = build_workflow_pack_queue_event_detail(queue_item_id=lease.queue_item_id)

    assert [event.event_type.value for event in history.events] == [
        "ADMISSION_REQUESTED",
        "ADMISSION_QUEUED",
        "ADMISSION_ADMITTED",
        "ADMISSION_GRANTED",
        "ADMISSION_RELEASED",
    ]
    assert [event.state.value for event in history.events] == [
        "NOT_ADMITTED",
        "QUEUED",
        "ADMITTED",
        "RUNNING",
        "COMPLETED_HANDOFF",
    ]
    assert history.events[0].caller_app == "lotus-gateway"
    assert history.events[0].correlation_id == "corr-queue-admission-1"
    assert history.events[0].tenant_id == "tenant-sg-001"
    assert history.events[0].workflow_surface == "advisor-brief-panel"
    assert history.events[2].caller_app == "lotus-gateway"
    assert history.events[2].correlation_id == "corr-queue-admission-1"


def test_queue_admission_rejects_lane_capacity_without_creating_extra_lease() -> None:
    registration = _advisor_brief_registration()
    first_lease = acquire_workflow_pack_queue_admission(registration=registration)
    second_lease = acquire_workflow_pack_queue_admission(registration=registration)

    try:
        try:
            acquire_workflow_pack_queue_admission(registration=registration)
        except HTTPException as exc:
            assert exc.status_code == 429
            assert "max_concurrent_runs_per_lane" in str(exc.detail)
            assert "advisor_brief.pack@v1" in str(exc.detail)
        else:
            raise AssertionError("Expected queue admission to reject full lane capacity")
    finally:
        release_workflow_pack_queue_admission(first_lease.queue_item_id)
        release_workflow_pack_queue_admission(second_lease.queue_item_id)

    rejected_history = _queue_events_for_reason("MAX_CONCURRENT_RUNS_PER_LANE")
    assert rejected_history[0].state.value == "REJECTED"
    assert rejected_history[0].workflow_pack_id == "advisor_brief.pack"


def test_queue_admission_rejects_unsupported_requested_lane() -> None:
    try:
        acquire_workflow_pack_queue_admission(
            registration=_advisor_brief_registration(),
            requested_lane=WorkflowPackQueueLane.NIGHTLY,
        )
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "not allowed" in str(exc.detail)
    else:
        raise AssertionError("Expected unsupported queue lane to fail admission")

    rejected_history = _queue_events_for_reason("QUEUE_LANE_NOT_ALLOWED")
    assert rejected_history[0].lane == WorkflowPackQueueLane.NIGHTLY


def test_queue_admission_release_records_timeout_terminal_posture() -> None:
    lease = acquire_workflow_pack_queue_admission(registration=_advisor_brief_registration())

    release_workflow_pack_queue_admission(
        lease.queue_item_id,
        now_utc=datetime.fromisoformat(lease.admitted_at.replace("Z", "+00:00"))
        + timedelta(minutes=10),
    )

    history = build_workflow_pack_queue_event_detail(queue_item_id=lease.queue_item_id)
    assert history.events[-1].event_type.value == "ADMISSION_TIMED_OUT"
    assert history.events[-1].state.value == "TIMED_OUT"
    assert history.events[-1].reason_code == "EXECUTION_TIMEOUT"


def test_queue_admission_cancellation_records_terminal_posture_and_releases_capacity() -> None:
    lease = acquire_workflow_pack_queue_admission(registration=_advisor_brief_registration())

    cancelled = cancel_workflow_pack_queue_admission(
        lease.queue_item_id,
        actor=WorkflowPackQueueCancellationActor.OPERATOR,
        reason="Operator stopped stale support request.",
        evidence_ref="support-ticket-123",
    )

    assert cancelled is True
    history = build_workflow_pack_queue_event_detail(queue_item_id=lease.queue_item_id)
    assert history.events[-1].event_type.value == "ADMISSION_CANCELLED"
    assert history.events[-1].state.value == "CANCELLED"
    assert history.events[-1].reason_code == "QUEUE_ADMISSION_CANCELLED"


def test_queue_admission_cancellation_requires_reason_and_evidence() -> None:
    lease = acquire_workflow_pack_queue_admission(registration=_advisor_brief_registration())

    try:
        cancel_workflow_pack_queue_admission(
            lease.queue_item_id,
            actor=WorkflowPackQueueCancellationActor.OPERATOR,
            reason=" ",
            evidence_ref="support-ticket-123",
        )
    except HTTPException as exc:
        assert exc.status_code == 422
        assert "requires non-empty reason and evidence_ref" in str(exc.detail)
    else:
        raise AssertionError("Expected queue cancellation without reason to fail")
    finally:
        release_workflow_pack_queue_admission(lease.queue_item_id)


def _queue_events_for_reason(reason_code: str) -> list[WorkflowPackQueueEventDescriptor]:
    return [
        event
        for event in build_workflow_pack_queue_event_catalog(
            workflow_pack_id="advisor_brief.pack"
        ).events
        if event.reason_code == reason_code
    ]
