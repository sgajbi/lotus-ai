from fastapi import HTTPException

from app.contracts.workflow_packs import (
    WorkflowPackActivationState,
    WorkflowPackControlActionRequest,
    WorkflowPackControlActionType,
)
from app.services.workflow_pack_control import (
    apply_workflow_pack_control_action,
    build_workflow_pack_control_history,
)
from app.services.workflow_pack_registry import get_workflow_pack_registration


def test_apply_workflow_pack_control_action_records_pause_and_resume_history() -> None:
    pause_response = apply_workflow_pack_control_action(
        WorkflowPackControlActionRequest(
            pack_id="advisor_brief.pack",
            version="v1",
            action_type=WorkflowPackControlActionType.PAUSE,
            caller_app="lotus-platform",
            requested_by="operator-a",
            approved_by="approver-a",
            reason="Pause pilot rollout during validation review.",
        )
    )

    assert pause_response.registration.activation_state == WorkflowPackActivationState.PAUSED
    assert pause_response.event.prior_activation_state == WorkflowPackActivationState.PILOT
    assert pause_response.event.resulting_activation_state == WorkflowPackActivationState.PAUSED

    resume_response = apply_workflow_pack_control_action(
        WorkflowPackControlActionRequest(
            pack_id="advisor_brief.pack",
            version="v1",
            action_type=WorkflowPackControlActionType.RESUME,
            caller_app="lotus-platform",
            requested_by="operator-a",
            approved_by="approver-a",
            reason="Resume after validation review.",
        )
    )

    assert resume_response.registration.activation_state == WorkflowPackActivationState.PILOT
    history = build_workflow_pack_control_history(
        pack_id="advisor_brief.pack",
        version="v1",
        limit=10,
    )
    assert len(history.latest_events) >= 2
    assert history.latest_events[0].action_type == WorkflowPackControlActionType.RESUME


def test_apply_workflow_pack_control_action_retires_registration() -> None:
    response = apply_workflow_pack_control_action(
        WorkflowPackControlActionRequest(
            pack_id="advisor_brief.pack",
            version="v2",
            action_type=WorkflowPackControlActionType.RETIRE,
            caller_app="lotus-platform",
            requested_by="operator-b",
            approved_by="approver-b",
            reason="Retire discovered candidate after superseding decision.",
        )
    )

    assert response.registration.activation_state == WorkflowPackActivationState.RETIRED
    refreshed = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v2")
    assert refreshed is not None
    assert refreshed.activation_state == WorkflowPackActivationState.RETIRED


def test_apply_workflow_pack_control_action_blocks_non_operator_caller() -> None:
    try:
        apply_workflow_pack_control_action(
            WorkflowPackControlActionRequest(
                pack_id="advisor_brief.pack",
                version="v1",
                action_type=WorkflowPackControlActionType.DEPRECATE,
                caller_app="lotus-manage",
                requested_by="operator-c",
                approved_by="approver-c",
                reason="Non-operator caller should be blocked.",
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("Expected non-operator workflow-pack control caller to be blocked")
