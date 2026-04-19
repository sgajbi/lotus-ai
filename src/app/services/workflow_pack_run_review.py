from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunEventType,
    WorkflowPackRunReviewActionRequest,
    WorkflowPackRunReviewActionResponse,
    WorkflowPackRunReviewActionType,
    WorkflowPackRunReviewState,
)
from app.repositories.workflow_pack_run_repository import (
    WorkflowPackRunEventRecord,
    WorkflowPackRunRecord,
)
from app.services.workflow_pack_run_ledger import (
    map_workflow_pack_run_event_record,
    map_workflow_pack_run_record,
)
from app.services.workflow_pack_run_store import get_workflow_pack_run_store

_OPERATOR_CALLER_APP = "lotus-platform"


def apply_workflow_pack_run_review_action(
    *,
    run_id: str,
    request: WorkflowPackRunReviewActionRequest,
) -> WorkflowPackRunReviewActionResponse:
    store = get_workflow_pack_run_store()
    run = store.get_run(run_id=run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown workflow-pack run: {run_id}",
        )

    _require_review_caller(run=run, caller_app=request.caller_app)

    replacement_run: WorkflowPackRunRecord | None = None
    if request.action_type in {
        WorkflowPackRunReviewActionType.REVISE,
        WorkflowPackRunReviewActionType.SUPERSEDE,
    }:
        replacement_run = _require_replacement_run(
            run=run,
            replacement_run_id=request.replacement_run_id,
        )
    elif request.replacement_run_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "replacement_run_id is only allowed for REVISE or SUPERSEDE review-state actions."
            ),
        )

    updated_run, recorded_events = _apply_review_transition(
        run=run,
        request=request,
        replacement_run=replacement_run,
    )
    store.save_run(updated_run)
    for event in recorded_events:
        store.save_event(event)

    if replacement_run is not None and request.replacement_run_id is not None:
        updated_replacement_run = replace(
            replacement_run,
            supersedes_run_id=run.run_id,
            last_updated_at=_utcnow(),
        )
        store.save_run(updated_replacement_run)
        replacement_event = WorkflowPackRunEventRecord(
            event_id=f"workflow_pack_run_evt_{uuid4().hex[:12]}",
            run_id=updated_replacement_run.run_id,
            event_type=WorkflowPackRunEventType.LINEAGE_UPDATED.value,
            runtime_state=updated_replacement_run.runtime_state,
            review_state=updated_replacement_run.review_state,
            actor=_actor_label(request.reviewed_by),
            message=(
                f"Workflow-pack run linked to predecessor `{run.run_id}` through "
                f"`{request.action_type.value}` review-state lineage. Reason: {request.reason}"
            ),
            recorded_at=_utcnow(),
        )
        store.save_event(replacement_event)
        recorded_events.append(replacement_event)

    return WorkflowPackRunReviewActionResponse(
        service=settings.service_name,
        version=settings.service_version,
        run=map_workflow_pack_run_record(updated_run),
        events=[map_workflow_pack_run_event_record(event) for event in recorded_events],
        summary=[
            f"Recorded workflow-pack review action `{request.action_type.value}` for `{run.run_id}`.",
            f"Review state moved from `{run.review_state}` to `{updated_run.review_state}`.",
            f"Review posture was recorded by `{request.reviewed_by}` for caller `{request.caller_app}`.",
            f"Recorded reason: {request.reason}",
        ],
    )


def _apply_review_transition(
    *,
    run: WorkflowPackRunRecord,
    request: WorkflowPackRunReviewActionRequest,
    replacement_run: WorkflowPackRunRecord | None,
) -> tuple[WorkflowPackRunRecord, list[WorkflowPackRunEventRecord]]:
    current_state = WorkflowPackRunReviewState(run.review_state)
    target_state = _resolve_target_review_state(request.action_type)
    _validate_review_transition(
        current_state=current_state,
        target_state=target_state,
        action_type=request.action_type,
    )

    now = _utcnow()
    updated_run = replace(
        run,
        review_state=target_state.value,
        superseded_by_run_id=(
            replacement_run.run_id if replacement_run is not None else run.superseded_by_run_id
        ),
        last_updated_at=now,
    )
    events = [
        WorkflowPackRunEventRecord(
            event_id=f"workflow_pack_run_evt_{uuid4().hex[:12]}",
            run_id=run.run_id,
            event_type=WorkflowPackRunEventType.REVIEW_STATE_UPDATED.value,
            runtime_state=updated_run.runtime_state,
            review_state=updated_run.review_state,
            actor=_actor_label(request.reviewed_by),
            message=(
                f"Workflow-pack review state changed from `{current_state.value}` to "
                f"`{target_state.value}` through `{request.action_type.value}`. "
                f"Reason: {request.reason}"
            ),
            recorded_at=now,
        )
    ]
    if replacement_run is not None:
        events.append(
            WorkflowPackRunEventRecord(
                event_id=f"workflow_pack_run_evt_{uuid4().hex[:12]}",
                run_id=run.run_id,
                event_type=WorkflowPackRunEventType.LINEAGE_UPDATED.value,
                runtime_state=updated_run.runtime_state,
                review_state=updated_run.review_state,
                actor=_actor_label(request.reviewed_by),
                message=(
                    f"Workflow-pack run linked to replacement run `{replacement_run.run_id}` through "
                    f"`{request.action_type.value}` review-state lineage. Reason: {request.reason}"
                ),
                recorded_at=now,
            )
        )
    return updated_run, events


def _resolve_target_review_state(
    action_type: WorkflowPackRunReviewActionType,
) -> WorkflowPackRunReviewState:
    mapping = {
        WorkflowPackRunReviewActionType.ACCEPT: WorkflowPackRunReviewState.ACCEPTED,
        WorkflowPackRunReviewActionType.REJECT: WorkflowPackRunReviewState.REJECTED,
        WorkflowPackRunReviewActionType.REVISE: WorkflowPackRunReviewState.REVISED,
        WorkflowPackRunReviewActionType.SUPERSEDE: WorkflowPackRunReviewState.SUPERSEDED,
        WorkflowPackRunReviewActionType.ABANDON: WorkflowPackRunReviewState.ABANDONED,
    }
    return mapping[action_type]


def _validate_review_transition(
    *,
    current_state: WorkflowPackRunReviewState,
    target_state: WorkflowPackRunReviewState,
    action_type: WorkflowPackRunReviewActionType,
) -> None:
    allowed_from_awaiting = {
        WorkflowPackRunReviewState.ACCEPTED,
        WorkflowPackRunReviewState.REJECTED,
        WorkflowPackRunReviewState.REVISED,
        WorkflowPackRunReviewState.SUPERSEDED,
        WorkflowPackRunReviewState.ABANDONED,
    }
    allowed_from_accepted = {WorkflowPackRunReviewState.SUPERSEDED}
    if (
        current_state == WorkflowPackRunReviewState.AWAITING_REVIEW
        and target_state in allowed_from_awaiting
    ):
        return
    if (
        current_state == WorkflowPackRunReviewState.ACCEPTED
        and target_state in allowed_from_accepted
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"Workflow-pack run review action `{action_type.value}` cannot move review state "
            f"from `{current_state.value}` to `{target_state.value}`."
        ),
    )


def _require_review_caller(*, run: WorkflowPackRunRecord, caller_app: str) -> None:
    if caller_app in {run.caller_app, _OPERATOR_CALLER_APP}:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "Workflow-pack review-state actions are currently limited to the original caller app "
            "or the lotus-platform operator caller while downstream review integration remains bounded."
        ),
    )


def _require_replacement_run(
    *,
    run: WorkflowPackRunRecord,
    replacement_run_id: str | None,
) -> WorkflowPackRunRecord:
    if not replacement_run_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="replacement_run_id is required for REVISE or SUPERSEDE review-state actions.",
        )
    replacement_run = get_workflow_pack_run_store().get_run(run_id=replacement_run_id)
    if replacement_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown replacement workflow-pack run: {replacement_run_id}",
        )
    if replacement_run.run_id == run.run_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A workflow-pack run cannot point to itself as replacement lineage.",
        )
    if replacement_run.pack_family != run.pack_family:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Replacement workflow-pack run must belong to the same pack family to preserve "
                "bounded review-state lineage."
            ),
        )
    if replacement_run.supersedes_run_id not in {None, run.run_id}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Replacement workflow-pack run `{replacement_run_id}` is already linked to "
                f"`{replacement_run.supersedes_run_id}`."
            ),
        )
    return replacement_run


def _actor_label(reviewed_by: str) -> str:
    return f"review:{reviewed_by}"


def _utcnow() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
