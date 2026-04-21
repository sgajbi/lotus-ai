from __future__ import annotations

from app.contracts.workflow_pack_runs import (
    WorkflowPackRunReviewActionType,
    WorkflowPackRunReviewState,
)


def resolve_allowed_review_actions(
    *,
    review_required: bool,
    review_state: WorkflowPackRunReviewState,
) -> list[WorkflowPackRunReviewActionType]:
    if not review_required:
        return []
    if review_state == WorkflowPackRunReviewState.AWAITING_REVIEW:
        return [
            WorkflowPackRunReviewActionType.ACCEPT,
            WorkflowPackRunReviewActionType.REJECT,
            WorkflowPackRunReviewActionType.REVISE,
            WorkflowPackRunReviewActionType.SUPERSEDE,
            WorkflowPackRunReviewActionType.ABANDON,
        ]
    if review_state == WorkflowPackRunReviewState.ACCEPTED:
        return [WorkflowPackRunReviewActionType.SUPERSEDE]
    return []
