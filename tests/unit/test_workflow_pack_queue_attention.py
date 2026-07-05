from datetime import UTC, datetime

from _pytest.monkeypatch import MonkeyPatch

from app.contracts.workflow_pack_queue_policies import (
    WorkflowPackQueueEventDescriptor,
    WorkflowPackQueueEventType,
    WorkflowPackQueueLane,
    WorkflowPackQueueLaneStatusDescriptor,
    WorkflowPackQueueSaturationStatus,
    WorkflowPackQueueState,
    WorkflowPackQueueStatusItemDescriptor,
    WorkflowPackQueueStatusResponse,
)
from app.services.workflow_pack_queue_attention import (
    _build_failure_cluster_attention_items,
    _build_recovery_blocked_attention_items,
    _build_terminal_queue_attention_items,
    _cluster_attention_reason,
    _cluster_attention_type,
    _recovery_blocked_event_to_attention_item,
    _terminal_event_to_attention_item,
    build_workflow_pack_queue_attention_summary,
)


def _queue_status(
    *,
    active_items: list[WorkflowPackQueueStatusItemDescriptor],
    lane_statuses: list[WorkflowPackQueueLaneStatusDescriptor] | None = None,
) -> WorkflowPackQueueStatusResponse:
    return WorkflowPackQueueStatusResponse(
        service="lotus-ai",
        version="0.1.0",
        phase="foundation",
        queue_source_mode="memory",
        active_admission_count=len(active_items),
        lane_statuses=lane_statuses or [],
        active_items=active_items,
        status_summary=["test queue posture"],
    )


def _queue_item(
    queue_item_id: str,
    *,
    admitted_at: str,
    workflow_pack_id: str = "advisor_brief.pack",
    workflow_pack_version: str = "v1",
) -> WorkflowPackQueueStatusItemDescriptor:
    return WorkflowPackQueueStatusItemDescriptor(
        queue_item_id=queue_item_id,
        policy_id="queue-policy.advisor-brief.v1",
        workflow_pack_id=workflow_pack_id,
        workflow_pack_version=workflow_pack_version,
        lane=WorkflowPackQueueLane.LATENCY_SENSITIVE,
        state=WorkflowPackQueueState.RUNNING,
        admitted_at=admitted_at,
    )


def _queue_event(
    event_type: WorkflowPackQueueEventType,
    *,
    lane: WorkflowPackQueueLane | None = WorkflowPackQueueLane.LATENCY_SENSITIVE,
    workflow_pack_id: str = "advisor_brief.pack",
    queue_item_id: str = "wpq_attention_event",
) -> WorkflowPackQueueEventDescriptor:
    return WorkflowPackQueueEventDescriptor(
        event_id=f"wpqe_{event_type.value.lower()}",
        queue_item_id=queue_item_id,
        event_type=event_type,
        policy_id="queue-policy.advisor-brief.v1",
        workflow_pack_id=workflow_pack_id,
        workflow_pack_version="v1",
        lane=lane,
        state=WorkflowPackQueueState.TIMED_OUT,
        caller_app="lotus-gateway",
        correlation_id="corr-attention-event",
        tenant_id="tenant-sg-001",
        workflow_surface="advisor-brief-panel",
        reason_code="TEST_REASON",
        source_queue_item_id=None,
        recovery_action_type=None,
        recovery_attempt_number=None,
        requested_by=None,
        evidence_ref=None,
        artifact_refs=[],
        message="test queue event",
        recorded_at="2026-04-21T12:00:00Z",
    )


def test_queue_attention_ignores_unknown_policy_and_non_stale_active_items(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.workflow_pack_queue_attention.build_workflow_pack_queue_status",
        lambda: _queue_status(
            active_items=[
                _queue_item(
                    "queue-recent",
                    admitted_at="2026-04-21T12:00:00Z",
                ),
                _queue_item(
                    "queue-unknown-policy",
                    admitted_at="not-a-timestamp",
                    workflow_pack_id="missing.pack",
                ),
            ],
        ),
    )

    summary = build_workflow_pack_queue_attention_summary(
        now_utc=datetime(2026, 4, 21, 12, 0, 30, tzinfo=UTC),
    )

    assert summary.heartbeat_status == "READY"
    assert summary.attention_count == 0
    assert summary.stale_item_count == 0
    assert summary.items == []


def test_queue_attention_treats_unparseable_admission_timestamp_as_stale(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.workflow_pack_queue_attention.build_workflow_pack_queue_status",
        lambda: _queue_status(
            active_items=[_queue_item("queue-invalid-time", admitted_at="not-a-timestamp")],
        ),
    )

    summary = build_workflow_pack_queue_attention_summary(
        now_utc=datetime(2026, 4, 21, 12, 0, tzinfo=UTC),
    )

    assert summary.heartbeat_status == "ATTENTION_REQUIRED"
    assert summary.attention_count == 1
    assert summary.stale_item_count == 1
    assert summary.items[0].queue_item_id == "queue-invalid-time"
    assert summary.items[0].admitted_at == "not-a-timestamp"


def test_queue_attention_normalizes_naive_timestamps_and_truncates_items(
    monkeypatch: MonkeyPatch,
) -> None:
    lane_status = WorkflowPackQueueLaneStatusDescriptor(
        policy_id="queue-policy.advisor-brief.v1",
        workflow_pack_id="advisor_brief.pack",
        workflow_pack_version="v1",
        lane=WorkflowPackQueueLane.LATENCY_SENSITIVE,
        active_count=2,
        max_concurrent_runs_per_lane=2,
        max_queued_runs_per_lane=20,
        saturation_attention_threshold=1.0,
        saturation_status=WorkflowPackQueueSaturationStatus.SATURATED,
    )
    stale_items = [
        _queue_item(f"queue-stale-{index}", admitted_at="2026-04-21T11:00:00")
        for index in range(1, 6)
    ]
    monkeypatch.setattr(
        "app.services.workflow_pack_queue_attention.build_workflow_pack_queue_status",
        lambda: _queue_status(active_items=stale_items, lane_statuses=[lane_status]),
    )

    summary = build_workflow_pack_queue_attention_summary(
        now_utc=datetime(2026, 4, 21, 12, 30, tzinfo=UTC),
    )

    assert summary.heartbeat_status == "ATTENTION_REQUIRED"
    assert summary.attention_count == 6
    assert summary.saturated_lane_count == 1
    assert summary.stale_item_count == 5
    assert len(summary.items) == summary.attention_limit == 5
    assert summary.items[0].attention_type == "LANE_SATURATED"
    assert [item.queue_item_id for item in summary.items[1:]] == [
        "queue-stale-1",
        "queue-stale-2",
        "queue-stale-3",
        "queue-stale-4",
    ]
    assert any("truncated" in line for line in summary.status_summary)


def test_queue_attention_maps_terminal_and_recovery_blocked_events() -> None:
    assert (
        _cluster_attention_type(WorkflowPackQueueEventType.ADMISSION_TIMED_OUT).value
        == "QUEUE_TIMEOUT_CLUSTER"
    )
    assert (
        _cluster_attention_type(WorkflowPackQueueEventType.ADMISSION_CANCELLED).value
        == "QUEUE_CANCELLATION_CLUSTER"
    )
    assert (
        _cluster_attention_type(WorkflowPackQueueEventType.RETRY_BLOCKED).value
        == "QUEUE_RECOVERY_BLOCKED_CLUSTER"
    )
    assert "timed out" in _cluster_attention_reason(
        event_type=WorkflowPackQueueEventType.ADMISSION_TIMED_OUT,
        event_count=3,
    )
    assert "cancelled" in _cluster_attention_reason(
        event_type=WorkflowPackQueueEventType.ADMISSION_CANCELLED,
        event_count=3,
    )
    assert "recovery decisions were blocked" in _cluster_attention_reason(
        event_type=WorkflowPackQueueEventType.RETRY_BLOCKED,
        event_count=3,
    )

    retry_item = _recovery_blocked_event_to_attention_item(
        _queue_event(WorkflowPackQueueEventType.RETRY_BLOCKED)
    )
    replay_item = _recovery_blocked_event_to_attention_item(
        _queue_event(WorkflowPackQueueEventType.REPLAY_BLOCKED)
    )
    timed_out_item = _terminal_event_to_attention_item(
        _queue_event(WorkflowPackQueueEventType.ADMISSION_TIMED_OUT)
    )
    cancelled_item = _terminal_event_to_attention_item(
        _queue_event(WorkflowPackQueueEventType.ADMISSION_CANCELLED)
    )
    degraded_item = _terminal_event_to_attention_item(
        _queue_event(WorkflowPackQueueEventType.ADMISSION_DEGRADED)
    )

    assert retry_item is not None
    assert retry_item.attention_type.value == "QUEUE_RETRY_BLOCKED"
    assert replay_item is not None
    assert replay_item.attention_type.value == "QUEUE_REPLAY_BLOCKED"
    assert timed_out_item is not None
    assert timed_out_item.attention_type.value == "QUEUE_ITEM_TIMED_OUT"
    assert cancelled_item is not None
    assert cancelled_item.attention_type.value == "QUEUE_ITEM_CANCELLED"
    assert degraded_item is not None
    assert degraded_item.attention_type.value == "QUEUE_ITEM_DEGRADED"

    assert (
        _recovery_blocked_event_to_attention_item(
            _queue_event(WorkflowPackQueueEventType.RETRY_BLOCKED, lane=None)
        )
        is None
    )
    assert (
        _terminal_event_to_attention_item(
            _queue_event(WorkflowPackQueueEventType.ADMISSION_TIMED_OUT, lane=None)
        )
        is None
    )
    assert (
        _recovery_blocked_event_to_attention_item(
            _queue_event(
                WorkflowPackQueueEventType.RETRY_BLOCKED,
                workflow_pack_id="missing.pack",
            )
        )
        is None
    )
    assert (
        _terminal_event_to_attention_item(
            _queue_event(
                WorkflowPackQueueEventType.ADMISSION_TIMED_OUT,
                workflow_pack_id="missing.pack",
            )
        )
        is None
    )


def test_queue_attention_deduplicates_terminal_and_recovery_blocked_events() -> None:
    timed_out = _queue_event(
        WorkflowPackQueueEventType.ADMISSION_TIMED_OUT,
        queue_item_id="queue-duplicate-terminal",
    )
    retry_blocked = _queue_event(
        WorkflowPackQueueEventType.RETRY_BLOCKED,
        queue_item_id="queue-duplicate-retry",
    )

    terminal_items = _build_terminal_queue_attention_items(events=[timed_out, timed_out])
    recovery_items = _build_recovery_blocked_attention_items(events=[retry_blocked, retry_blocked])

    assert len(terminal_items) == 1
    assert terminal_items[0].queue_item_id == "queue-duplicate-terminal"
    assert len(recovery_items) == 1
    assert recovery_items[0].queue_item_id == "queue-duplicate-retry"


def test_queue_attention_failure_cluster_skips_events_without_policy_or_lane() -> None:
    no_lane_events = [
        _queue_event(
            WorkflowPackQueueEventType.ADMISSION_TIMED_OUT,
            lane=None,
            queue_item_id=f"queue-no-lane-{index}",
        )
        for index in range(3)
    ]
    missing_policy_events = [
        _queue_event(
            WorkflowPackQueueEventType.ADMISSION_TIMED_OUT,
            workflow_pack_id="missing.pack",
            queue_item_id=f"queue-missing-policy-{index}",
        )
        for index in range(3)
    ]

    assert _build_failure_cluster_attention_items(events=no_lane_events) == []
    assert _build_failure_cluster_attention_items(events=missing_policy_events) == []
