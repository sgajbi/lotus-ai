from fastapi import HTTPException

from app.contracts.workflow_packs import (
    WorkflowPackActivationState,
    WorkflowPackControlActionRequest,
    WorkflowPackControlActionType,
    WorkflowPackRegistrationStatus,
)
from app.services.workflow_pack_control import (
    apply_workflow_pack_control_action,
    build_workflow_pack_control_history,
)
from app.services.workflow_pack_registry import (
    get_workflow_pack_registration,
    save_workflow_pack_registration,
)


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
    assert pause_response.event.authorization.caller_app == "lotus-platform"
    assert pause_response.event.authorization.allowed is True

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
    assert response.event.authorization.outcome.value == "ALLOWED"
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
        assert "not authorized for async control-plane actions" in exc.detail
    else:
        raise AssertionError("Expected non-operator workflow-pack control caller to be blocked")


def test_apply_workflow_pack_control_action_rejects_unknown_registration() -> None:
    try:
        apply_workflow_pack_control_action(
            WorkflowPackControlActionRequest(
                pack_id="missing.pack",
                version="v1",
                action_type=WorkflowPackControlActionType.PAUSE,
                caller_app="lotus-platform",
                requested_by="operator-d",
                approved_by="approver-d",
                reason="Unknown registration should fail.",
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected unknown workflow-pack registration to return 404")


def test_apply_workflow_pack_control_action_rejects_resume_when_not_paused() -> None:
    try:
        apply_workflow_pack_control_action(
            WorkflowPackControlActionRequest(
                pack_id="advisor_brief.pack",
                version="v1",
                action_type=WorkflowPackControlActionType.RESUME,
                caller_app="lotus-platform",
                requested_by="operator-e",
                approved_by="approver-e",
                reason="Resume should fail when registration is not paused.",
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError("Expected resume without pause to fail")


def test_apply_workflow_pack_control_action_rejects_pause_from_dark_state() -> None:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    save_workflow_pack_registration(
        registration.model_copy(
            update={
                "activation_state": WorkflowPackActivationState.DARK,
                "pause_state": "NOT_PAUSED",
            }
        )
    )

    try:
        apply_workflow_pack_control_action(
            WorkflowPackControlActionRequest(
                pack_id="advisor_brief.pack",
                version="v1",
                action_type=WorkflowPackControlActionType.PAUSE,
                caller_app="lotus-platform",
                requested_by="operator-f",
                approved_by="approver-f",
                reason="Pause should fail from dark state.",
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError("Expected pause from dark state to fail")


def test_apply_workflow_pack_control_action_rejects_deprecate_after_retire() -> None:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v2")
    assert registration is not None
    save_workflow_pack_registration(
        registration.model_copy(
            update={
                "registration_status": WorkflowPackRegistrationStatus.RETIRED,
                "activation_state": WorkflowPackActivationState.RETIRED,
            }
        )
    )

    try:
        apply_workflow_pack_control_action(
            WorkflowPackControlActionRequest(
                pack_id="advisor_brief.pack",
                version="v2",
                action_type=WorkflowPackControlActionType.DEPRECATE,
                caller_app="lotus-platform",
                requested_by="operator-g",
                approved_by="approver-g",
                reason="Deprecate should fail once retired.",
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError("Expected deprecate on retired registration to fail")
