from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from app.services.workflow_pack_queue_admission import (
    acquire_workflow_pack_queue_admission,
    cancel_workflow_pack_queue_admission,
    release_workflow_pack_queue_admission,
)
from app.services.workflow_pack_queue_admission_models import (
    WorkflowPackQueueAdmissionLease,
)
from app.contracts.workflow_pack_queue_policies import WorkflowPackQueueCancellationActor
from app.services.workflow_pack_queue_attention import build_workflow_pack_queue_attention_summary
from app.services.workflow_pack_queue_events import build_workflow_pack_queue_event_detail
from app.services.workflow_pack_queue_recovery import (
    REPLAY_BLOCKED_REASON_CODE,
    RETRY_BLOCKED_REASON_CODE,
    _latest_terminal_event,
    _load_history,
    _resolve_policy,
    record_workflow_pack_queue_replay_decision,
    record_workflow_pack_queue_retry_decision,
)
from app.services.workflow_pack_registry import get_workflow_pack_registration


def test_queue_retry_records_once_then_blocks_retry_amplification() -> None:
    queue_item_id = _timed_out_advisor_brief_queue_item()

    retry_event = record_workflow_pack_queue_retry_decision(
        queue_item_id=queue_item_id,
        caller_app="lotus-platform",
        failure_code="EXECUTION_TIMEOUT",
        requested_by="operator-a",
        reason="Retry once after timeout investigation.",
        evidence_ref="support-ticket-queue-retry-1",
    )
    blocked_event = record_workflow_pack_queue_retry_decision(
        queue_item_id=queue_item_id,
        caller_app="lotus-platform",
        failure_code="EXECUTION_TIMEOUT",
        requested_by="operator-a",
        reason="Second retry would exceed queue policy.",
        evidence_ref="support-ticket-queue-retry-2",
    )

    history = build_workflow_pack_queue_event_detail(queue_item_id=queue_item_id)
    assert retry_event.event_type.value == "RETRY_RECORDED"
    assert retry_event.state.value == "QUEUED"
    assert retry_event.source_queue_item_id == queue_item_id
    assert retry_event.recovery_action_type is not None
    assert retry_event.recovery_action_type.value == "RETRY"
    assert retry_event.recovery_attempt_number == 1
    assert blocked_event.event_type.value == "RETRY_BLOCKED"
    assert blocked_event.reason_code == RETRY_BLOCKED_REASON_CODE
    assert blocked_event.recovery_attempt_number == 2
    assert [event.event_type.value for event in history.events][-2:] == [
        "RETRY_RECORDED",
        "RETRY_BLOCKED",
    ]


def test_queue_retry_blocks_non_retryable_failure_code() -> None:
    queue_item_id = _timed_out_advisor_brief_queue_item()

    blocked_event = record_workflow_pack_queue_retry_decision(
        queue_item_id=queue_item_id,
        caller_app="lotus-platform",
        failure_code="CALLER_NOT_AUTHORIZED",
        requested_by="operator-a",
        reason="Caller policy failure must not be retried.",
        evidence_ref="support-ticket-queue-retry-3",
    )

    assert blocked_event.event_type.value == "RETRY_BLOCKED"
    assert blocked_event.reason_code == RETRY_BLOCKED_REASON_CODE
    assert blocked_event.state.value == "TIMED_OUT"


def test_queue_retry_blocks_completed_handoff_even_with_retryable_failure_code() -> None:
    queue_item_id = _completed_advisor_brief_queue_item()

    blocked_event = record_workflow_pack_queue_retry_decision(
        queue_item_id=queue_item_id,
        caller_app="lotus-platform",
        failure_code="EXECUTION_TIMEOUT",
        requested_by="operator-a",
        reason="Completed handoff should use replay, not retry.",
        evidence_ref="support-ticket-queue-retry-completed",
    )

    assert blocked_event.event_type.value == "RETRY_BLOCKED"
    assert blocked_event.reason_code == RETRY_BLOCKED_REASON_CODE
    assert blocked_event.state.value == "COMPLETED_HANDOFF"


def test_queue_replay_records_once_then_blocks_duplicate_replay() -> None:
    queue_item_id = _completed_advisor_brief_queue_item()

    replay_event = record_workflow_pack_queue_replay_decision(
        queue_item_id=queue_item_id,
        caller_app="lotus-platform",
        requested_by="operator-a",
        reason="Replay for controlled evidence comparison.",
        evidence_ref="support-ticket-queue-replay-1",
    )
    blocked_event = record_workflow_pack_queue_replay_decision(
        queue_item_id=queue_item_id,
        caller_app="lotus-platform",
        requested_by="operator-a",
        reason="Duplicate replay should be blocked.",
        evidence_ref="support-ticket-queue-replay-2",
    )

    assert replay_event.event_type.value == "REPLAY_RECORDED"
    assert replay_event.state.value == "QUEUED"
    assert replay_event.recovery_action_type is not None
    assert replay_event.recovery_action_type.value == "REPLAY"
    assert blocked_event.event_type.value == "REPLAY_BLOCKED"
    assert blocked_event.reason_code == REPLAY_BLOCKED_REASON_CODE


def test_queue_recovery_requires_actor_reason_and_evidence() -> None:
    queue_item_id = _timed_out_advisor_brief_queue_item()

    with pytest.raises(HTTPException) as exc_info:
        record_workflow_pack_queue_retry_decision(
            queue_item_id=queue_item_id,
            caller_app="lotus-platform",
            failure_code="EXECUTION_TIMEOUT",
            requested_by="operator-a",
            reason=" ",
            evidence_ref="support-ticket-queue-retry-4",
        )

    assert exc_info.value.status_code == 422
    assert "requires non-empty requested_by, reason, and evidence_ref" in str(exc_info.value.detail)


def test_queue_recovery_reports_missing_history_terminal_event_and_policy() -> None:
    with pytest.raises(HTTPException) as missing_history:
        _load_history("missing-queue-item")
    assert missing_history.value.status_code == 404

    active_lease = _acquire_advisor_brief_lease()
    active_history = build_workflow_pack_queue_event_detail(
        queue_item_id=active_lease.queue_item_id
    )
    with pytest.raises(HTTPException) as non_terminal:
        _latest_terminal_event(active_history.events)
    assert non_terminal.value.status_code == 409
    assert "terminal queue event" in str(non_terminal.value.detail)

    timed_out_queue_item_id = _timed_out_advisor_brief_queue_item()
    timed_out_history = build_workflow_pack_queue_event_detail(
        queue_item_id=timed_out_queue_item_id
    )
    terminal_event = _latest_terminal_event(timed_out_history.events)
    missing_policy_event = terminal_event.model_copy(
        update={"workflow_pack_id": "missing.pack", "workflow_pack_version": "v404"}
    )
    with pytest.raises(HTTPException) as missing_policy:
        _resolve_policy(missing_policy_event)
    assert missing_policy.value.status_code == 409
    assert "declared queue policy" in str(missing_policy.value.detail)


def test_queue_attention_surfaces_blocked_retry_and_replay() -> None:
    retry_queue_item_id = _timed_out_advisor_brief_queue_item()
    record_workflow_pack_queue_retry_decision(
        queue_item_id=retry_queue_item_id,
        caller_app="lotus-platform",
        failure_code="CALLER_NOT_AUTHORIZED",
        requested_by="operator-a",
        reason="Caller policy failure must not be retried.",
        evidence_ref="support-ticket-queue-retry-5",
    )
    replay_queue_item_id = _completed_advisor_brief_queue_item()
    record_workflow_pack_queue_replay_decision(
        queue_item_id=replay_queue_item_id,
        caller_app="lotus-platform",
        requested_by="operator-a",
        reason="Replay for controlled evidence comparison.",
        evidence_ref="support-ticket-queue-replay-3",
    )
    record_workflow_pack_queue_replay_decision(
        queue_item_id=replay_queue_item_id,
        caller_app="lotus-platform",
        requested_by="operator-a",
        reason="Duplicate replay should be blocked.",
        evidence_ref="support-ticket-queue-replay-4",
    )

    summary = build_workflow_pack_queue_attention_summary()

    assert summary.heartbeat_status == "ATTENTION_REQUIRED"
    assert summary.recovery_blocked_count == 2
    assert [
        item.attention_type
        for item in summary.items
        if item.attention_type in {"QUEUE_RETRY_BLOCKED", "QUEUE_REPLAY_BLOCKED"}
    ] == ["QUEUE_REPLAY_BLOCKED", "QUEUE_RETRY_BLOCKED"]


def test_queue_attention_surfaces_repeated_failure_clusters() -> None:
    _timed_out_advisor_brief_queue_item()
    _timed_out_advisor_brief_queue_item()
    _cancelled_advisor_brief_queue_item("support-ticket-queue-cancel-cluster-1")
    _cancelled_advisor_brief_queue_item("support-ticket-queue-cancel-cluster-2")

    summary = build_workflow_pack_queue_attention_summary()

    cluster_items = [
        item
        for item in summary.items
        if item.attention_type
        in {
            "QUEUE_TIMEOUT_CLUSTER",
            "QUEUE_CANCELLATION_CLUSTER",
        }
    ]
    assert summary.failure_cluster_count == 2
    assert [item.attention_type for item in cluster_items] == [
        "QUEUE_CANCELLATION_CLUSTER",
        "QUEUE_TIMEOUT_CLUSTER",
    ]
    assert all(item.active_count == 0 for item in cluster_items)
    assert all(item.event_count == 2 for item in cluster_items)
    assert all(item.queue_item_id is None for item in cluster_items)


def test_queue_attention_reports_sampled_event_window_when_older_attention_is_outside_sample() -> (
    None
):
    retry_queue_item_id = _timed_out_advisor_brief_queue_item()
    record_workflow_pack_queue_retry_decision(
        queue_item_id=retry_queue_item_id,
        caller_app="lotus-platform",
        failure_code="CALLER_NOT_AUTHORIZED",
        requested_by="operator-a",
        reason="Caller policy failure must not be retried.",
        evidence_ref="support-ticket-queue-retry-sampled-window",
    )
    for _ in range(101):
        _completed_advisor_brief_queue_item()

    summary = build_workflow_pack_queue_attention_summary()

    assert summary.event_sample_limit == 100
    assert summary.event_sample_count == 100
    assert summary.event_window_truncated is True
    assert summary.recovery_blocked_count == 0
    assert any("bounded sample" in line for line in summary.status_summary)


def _timed_out_advisor_brief_queue_item() -> str:
    lease = _acquire_advisor_brief_lease()
    release_workflow_pack_queue_admission(
        lease.queue_item_id,
        now_utc=datetime.now(UTC) + timedelta(minutes=10),
    )
    return lease.queue_item_id


def _completed_advisor_brief_queue_item() -> str:
    lease = _acquire_advisor_brief_lease()
    release_workflow_pack_queue_admission(lease.queue_item_id)
    return lease.queue_item_id


def _cancelled_advisor_brief_queue_item(evidence_ref: str) -> str:
    lease = _acquire_advisor_brief_lease()
    cancel_workflow_pack_queue_admission(
        lease.queue_item_id,
        actor=WorkflowPackQueueCancellationActor.OPERATOR,
        reason="Operator cancelled repeated queue admission.",
        evidence_ref=evidence_ref,
    )
    return lease.queue_item_id


def _acquire_advisor_brief_lease() -> WorkflowPackQueueAdmissionLease:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    return acquire_workflow_pack_queue_admission(registration=registration)
