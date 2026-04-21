from app.contracts.workflow_pack_runs import (
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
)
from app.services.workflow_pack_run_review_policy import resolve_allowed_review_actions


def test_resolve_allowed_review_actions_for_awaiting_review() -> None:
    actions = resolve_allowed_review_actions(
        review_required=True,
        review_state=WorkflowPackRunReviewState.AWAITING_REVIEW,
        runtime_state=WorkflowPackRunRuntimeState.COMPLETED,
    )

    assert [action.value for action in actions] == [
        "ACCEPT",
        "REJECT",
        "REVISE",
        "SUPERSEDE",
        "ABANDON",
    ]


def test_resolve_allowed_review_actions_for_accepted_run() -> None:
    actions = resolve_allowed_review_actions(
        review_required=True,
        review_state=WorkflowPackRunReviewState.ACCEPTED,
        runtime_state=WorkflowPackRunRuntimeState.COMPLETED,
    )

    assert [action.value for action in actions] == ["SUPERSEDE"]


def test_resolve_allowed_review_actions_returns_empty_for_non_reviewable_posture() -> None:
    assert (
        resolve_allowed_review_actions(
            review_required=False,
            review_state=WorkflowPackRunReviewState.NOT_REVIEW_REQUIRED,
            runtime_state=WorkflowPackRunRuntimeState.COMPLETED,
        )
        == []
    )
    assert (
        resolve_allowed_review_actions(
            review_required=True,
            review_state=WorkflowPackRunReviewState.SUPERSEDED,
            runtime_state=WorkflowPackRunRuntimeState.COMPLETED,
        )
        == []
    )


def test_resolve_allowed_review_actions_blocks_failed_runtime_posture() -> None:
    actions = resolve_allowed_review_actions(
        review_required=True,
        review_state=WorkflowPackRunReviewState.AWAITING_REVIEW,
        runtime_state=WorkflowPackRunRuntimeState.FAILED,
    )

    assert actions == []
