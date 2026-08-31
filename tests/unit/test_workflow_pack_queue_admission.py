from datetime import datetime, timedelta

from _pytest.monkeypatch import MonkeyPatch
from fastapi import HTTPException
from pytest import raises

from app.contracts.workflow_pack_queue_policies import (
    WorkflowPackQueueCancellationActor,
    WorkflowPackQueueEventDescriptor,
    WorkflowPackQueueEventType,
    WorkflowPackQueueLane,
    WorkflowPackQueueState,
)
from app.contracts.workflow_packs import WorkflowPackRegistrationDescriptor
from app.services.workflow_pack_queue_admission import (
    _ensure_queue_event_store_ready_for_admission,
    _record_queue_event,
    _transition_queue_state,
    acquire_workflow_pack_queue_admission,
    cancel_workflow_pack_queue_admission,
    release_workflow_pack_queue_admission,
)
from app.services.workflow_pack_queue_events import (
    WorkflowPackQueueEventStoreNotReadyError,
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


def test_queue_admission_rejects_registration_without_queue_policy(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.workflow_pack_queue_admission.get_workflow_pack_queue_policy_descriptor",
        lambda *, pack_id, version: None,
    )

    try:
        acquire_workflow_pack_queue_admission(
            registration=_advisor_brief_registration(),
            caller_app="lotus-gateway",
            correlation_id="corr-queue-policy-missing",
        )
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "queue policy is not declared" in str(exc.detail)
    else:
        raise AssertionError("expected missing queue policy to reject admission")

    rejected_history = _queue_events_for_reason("QUEUE_POLICY_NOT_FOUND")
    assert rejected_history[0].correlation_id == "corr-queue-policy-missing"


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


def test_queue_admission_cancellation_returns_false_for_unknown_lease() -> None:
    assert (
        cancel_workflow_pack_queue_admission(
            "wpq_missing",
            actor=WorkflowPackQueueCancellationActor.OPERATOR,
            reason="Operator searched for a missing queue item.",
            evidence_ref="support-ticket-missing-queue",
        )
        is False
    )


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


def test_queue_admission_defensive_failures_are_explicit(
    monkeypatch: MonkeyPatch,
) -> None:
    try:
        _transition_queue_state(
            current_state=WorkflowPackQueueState.COMPLETED_HANDOFF,
            next_state=WorkflowPackQueueState.RUNNING,
        )
    except RuntimeError as exc:
        assert "Illegal workflow-pack queue transition" in str(exc)
    else:
        raise AssertionError("expected illegal queue transition to fail explicitly")

    try:
        _record_queue_event(
            queue_item_id="wpq_missing_identity",
            event_type=WorkflowPackQueueEventType.ADMISSION_REJECTED,
            state=WorkflowPackQueueState.REJECTED,
            message="missing identity",
        )
    except RuntimeError as exc:
        assert "queue event identity is required" in str(exc)
    else:
        raise AssertionError("expected missing queue event identity to fail explicitly")

    monkeypatch.setattr(
        "app.services.workflow_pack_queue_admission.ensure_workflow_pack_queue_event_store_ready",
        lambda: (_ for _ in ()).throw(
            WorkflowPackQueueEventStoreNotReadyError("queue store not ready")
        ),
    )
    try:
        _ensure_queue_event_store_ready_for_admission()
    except HTTPException as exc:
        assert exc.status_code == 503
        assert "queue store not ready" in str(exc.detail)
    else:
        raise AssertionError("expected queue admission to fail when event store is unavailable")


def _queue_events_for_reason(reason_code: str) -> list[WorkflowPackQueueEventDescriptor]:
    return [
        event
        for event in build_workflow_pack_queue_event_catalog(
            workflow_pack_id="advisor_brief.pack"
        ).events
        if event.reason_code == reason_code
    ]


def test_a_lost_capacity_race_never_records_a_grant(monkeypatch: MonkeyPatch) -> None:
    """Losing the replica-atomic admit must read as a plain capacity
    rejection: the durable history previously showed granted-then-rejected
    for one queue item, in exactly the race the leases exist for (#228)."""

    from app.repositories.workflow_pack_admission_lease_repository import (
        WorkflowPackAdmissionAttempt,
    )
    from app.services import workflow_pack_queue_admission as admission

    from app.services.workflow_pack_admission_lease_store import (
        get_workflow_pack_admission_lease_repository,
    )

    real_repository = get_workflow_pack_admission_lease_repository()

    class _LosesTheRace:
        def __getattr__(self, name: str) -> object:
            return getattr(real_repository, name)

        def try_admit(self, lease: object, **_kwargs: object) -> WorkflowPackAdmissionAttempt:
            # Another replica took the last slot between the advisory check
            # and the authoritative admit.
            return WorkflowPackAdmissionAttempt(
                admitted=False, active_pack_count=99, active_lane_count=99
            )

    monkeypatch.setattr(
        admission, "get_workflow_pack_admission_lease_repository", lambda: _LosesTheRace()
    )

    with raises(HTTPException) as exc_info:
        acquire_workflow_pack_queue_admission(
            registration=_advisor_brief_registration(),
            caller_app="lotus-gateway",
            correlation_id="corr-lost-race",
            tenant_id="tenant-sg-001",
            workflow_surface="advisor-brief-panel",
        )

    assert exc_info.value.status_code == 429
    catalog = build_workflow_pack_queue_event_catalog(limit=20)
    lost_race_events = [
        event.event_type.value
        for event in catalog.events
        if event.correlation_id == "corr-lost-race"
    ]
    assert "ADMISSION_GRANTED" not in lost_race_events
    assert "ADMISSION_REJECTED" in lost_race_events


def test_a_reclaimed_lease_gets_a_terminal_event_in_its_own_history() -> None:
    """Capacity recovery must not be silent (#228): an item whose replica
    died ends its durable history with a reclamation event, so support can
    tell "died and was reclaimed" from "still running"."""

    from datetime import UTC
    from datetime import datetime as real_datetime

    from app.config import settings
    from app.services.workflow_pack_admission_lease_store import (
        get_workflow_pack_admission_lease_repository,
    )
    from app.services.workflow_pack_queue_admission_models import (
        WorkflowPackQueueAdmissionLease,
    )

    settings.workflow_pack_admission_lease_ttl_seconds = 60
    registration = _advisor_brief_registration()
    repository = get_workflow_pack_admission_lease_repository()
    abandoned_at = (real_datetime.now(UTC) - timedelta(seconds=3600)).isoformat()
    crashed = WorkflowPackQueueAdmissionLease(
        queue_item_id="wpq_crashed_replica",
        policy_id="queue-policy.advisor-brief.v1",
        workflow_pack_id="advisor_brief.pack",
        workflow_pack_version="v1",
        lane=WorkflowPackQueueLane.LATENCY_SENSITIVE,
        state=WorkflowPackQueueState.RUNNING,
        admitted_at=abandoned_at,
        caller_app="lotus-gateway",
        correlation_id="corr-crashed-replica",
        tenant_id="tenant-sg-001",
        workflow_surface="advisor-brief-panel",
    )
    assert repository.try_admit(crashed, pack_limit=5, lane_limit=5).admitted

    lease = acquire_workflow_pack_queue_admission(
        registration=registration,
        caller_app="lotus-gateway",
        correlation_id="corr-after-reclaim",
        tenant_id="tenant-sg-001",
        workflow_surface="advisor-brief-panel",
    )

    # Capacity recovered ...
    assert lease.queue_item_id != "wpq_crashed_replica"
    assert repository.get_lease("wpq_crashed_replica") is None
    # ... and the crashed item's own history says why it ended.
    crashed_history = build_workflow_pack_queue_event_detail(queue_item_id="wpq_crashed_replica")
    assert [event.event_type.value for event in crashed_history.events] == ["ADMISSION_RECLAIMED"]
    assert crashed_history.events[0].state.value == "TIMED_OUT"
    assert crashed_history.events[0].correlation_id == "corr-crashed-replica"


def test_the_lease_ttl_default_cannot_be_shorter_than_a_test_run() -> None:
    """The reclamation tests set an explicit TTL; the shipped default must
    stay far above any legitimate execution so nothing is reclaimed while
    it is still running."""

    from app.config import Settings

    assert Settings().workflow_pack_admission_lease_ttl_seconds >= 600
