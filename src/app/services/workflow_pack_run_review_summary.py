from __future__ import annotations

from app.contracts.workflow_pack_runs import (
    WorkflowPackRunConsumerReviewDescriptor,
    WorkflowPackRunEventType,
    WorkflowPackRunReviewState,
)
from app.repositories.workflow_pack_run_repository import (
    WorkflowPackRunEventRecord,
    WorkflowPackRunRecord,
)
from app.services.workflow_pack_run_review_policy import resolve_allowed_review_actions


def build_workflow_pack_run_review_descriptor(
    *,
    record: WorkflowPackRunRecord,
    events: list[WorkflowPackRunEventRecord],
) -> WorkflowPackRunConsumerReviewDescriptor:
    review_state = WorkflowPackRunReviewState(record.review_state)
    review_events = list_workflow_pack_run_review_events(events)
    latest_review_event = review_events[-1] if review_events else None
    return WorkflowPackRunConsumerReviewDescriptor(
        required=record.review_required,
        state=review_state,
        allowed_actions=resolve_allowed_review_actions(
            review_required=record.review_required,
            review_state=review_state,
        ),
        latest_review_event_at=(
            latest_review_event.recorded_at if latest_review_event is not None else None
        ),
        latest_review_actor=latest_review_event.actor if latest_review_event is not None else None,
        review_transition_count=len(review_events),
        has_review_history=bool(review_events),
    )


def list_workflow_pack_run_review_events(
    events: list[WorkflowPackRunEventRecord],
) -> list[WorkflowPackRunEventRecord]:
    return [
        event
        for event in events
        if event.event_type == WorkflowPackRunEventType.REVIEW_STATE_UPDATED.value
    ]
