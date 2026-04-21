from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.access_control import AuthorizationCapabilityType
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunEventType,
    WorkflowPackRunReviewActionRequest,
    WorkflowPackRunReviewActionResponse,
    WorkflowPackRunReviewActionType,
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
)
from app.repositories.workflow_pack_run_repository import (
    WorkflowPackRunEventRecord,
    WorkflowPackRunRecord,
    WorkflowPackRunRepository,
)
from app.services.access_control_authorization import (
    authorize_request,
    require_active_registered_caller,
    require_authorized,
)
from app.services.workflow_pack_run_ledger import (
    ensure_workflow_pack_run_store_ready,
    map_workflow_pack_run_event_record,
    map_workflow_pack_run_record,
)
from app.services.workflow_pack_run_review_policy import resolve_allowed_review_actions
from app.services.workflow_pack_run_supportability import (
    resolve_workflow_pack_run_record_supportability_status,
)
from app.services.workflow_pack_run_store import get_workflow_pack_run_store
from app.services.workflow_pack_task_flow_service import (
    ensure_workflow_pack_task_flow_store_ready,
    synchronize_task_flow_review_action,
)


def apply_workflow_pack_run_review_action(
    *,
    run_id: str,
    request: WorkflowPackRunReviewActionRequest,
) -> WorkflowPackRunReviewActionResponse:
    ensure_workflow_pack_run_store_ready()
    ensure_workflow_pack_task_flow_store_ready()
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
            store=store,
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

    synchronize_task_flow_review_action(
        run_id=updated_run.run_id,
        review_state=WorkflowPackRunReviewState(updated_run.review_state),
        supportability_status=resolve_workflow_pack_run_record_supportability_status(updated_run),
        action_type=request.action_type,
        reviewed_by=request.reviewed_by,
        reason=request.reason,
        recorded_at=recorded_events[0].recorded_at,
        replacement_run_id=replacement_run.run_id if replacement_run is not None else None,
    )

    return WorkflowPackRunReviewActionResponse(
        service=settings.service_name,
        version=settings.service_version,
        run=map_workflow_pack_run_record(updated_run, store=store),
        events=[map_workflow_pack_run_event_record(event) for event in recorded_events],
        summary=_build_review_action_summary(
            run=run,
            updated_run=updated_run,
            request=request,
            replacement_run=replacement_run,
        ),
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
        review_required=run.review_required,
        current_state=current_state,
        runtime_state=WorkflowPackRunRuntimeState(run.runtime_state),
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
    review_required: bool,
    current_state: WorkflowPackRunReviewState,
    runtime_state: WorkflowPackRunRuntimeState,
    action_type: WorkflowPackRunReviewActionType,
) -> None:
    if action_type in resolve_allowed_review_actions(
        review_required=review_required,
        review_state=current_state,
        runtime_state=runtime_state,
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"Workflow-pack run review action `{action_type.value}` is not allowed from "
            f"review state `{current_state.value}` and runtime state `{runtime_state.value}`."
        ),
    )


def _require_review_caller(*, run: WorkflowPackRunRecord, caller_app: str) -> None:
    blocked_summary = (
        "Workflow-pack review-state actions are currently limited to the original active "
        "registered caller app or a caller authorized for async control-plane actions while "
        "downstream review integration remains bounded."
    )
    if caller_app == run.caller_app:
        require_active_registered_caller(caller_app, blocked_summary=blocked_summary)
        return
    try:
        require_authorized(
            authorize_request(
                caller_app=caller_app,
                capability_type=AuthorizationCapabilityType.ASYNC_CONTROL,
            ),
        )
    except HTTPException as exc:
        raise HTTPException(status_code=exc.status_code, detail=blocked_summary) from exc


def _require_replacement_run(
    *,
    store: WorkflowPackRunRepository,
    run: WorkflowPackRunRecord,
    replacement_run_id: str | None,
) -> WorkflowPackRunRecord:
    if not replacement_run_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="replacement_run_id is required for REVISE or SUPERSEDE review-state actions.",
        )
    replacement_run = store.get_run(run_id=replacement_run_id)
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
    if (
        replacement_run.workflow_authority_owner != run.workflow_authority_owner
        or replacement_run.caller_app != run.caller_app
        or replacement_run.tenant_id != run.tenant_id
        or replacement_run.workflow_surface != run.workflow_surface
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Replacement workflow-pack run must preserve workflow authority owner, caller app, "
                "tenant scope, and workflow surface to keep review-state lineage inside one bounded "
                "downstream workflow."
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


def _build_review_action_summary(
    *,
    run: WorkflowPackRunRecord,
    updated_run: WorkflowPackRunRecord,
    request: WorkflowPackRunReviewActionRequest,
    replacement_run: WorkflowPackRunRecord | None,
) -> list[str]:
    summary = [
        f"Recorded workflow-pack review action `{request.action_type.value}` for `{run.run_id}`.",
        f"Review state moved from `{run.review_state}` to `{updated_run.review_state}`.",
        f"Review posture was recorded by `{request.reviewed_by}` for caller `{request.caller_app}`.",
        f"Recorded reason: {request.reason}",
    ]
    if replacement_run is not None:
        summary.append(
            f"Replacement lineage now points to `{replacement_run.run_id}` for bounded review-state traceability."
        )
    return summary


def _actor_label(reviewed_by: str) -> str:
    return f"review:{reviewed_by}"


def _utcnow() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
