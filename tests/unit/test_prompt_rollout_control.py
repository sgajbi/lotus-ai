from fastapi import HTTPException

from app.contracts.prompts import PromptControlActionRequest, PromptControlActionType
from app.services.prompt_rollout_control import (
    apply_prompt_control_action,
    build_prompt_control_history,
)
from app.services.prompt_runtime import resolve_runtime_prompt_or_raise
from app.services.prompt_store import reset_prompt_store_cache


def test_apply_prompt_control_action_promotes_candidate_and_records_history() -> None:
    reset_prompt_store_cache()

    response = apply_prompt_control_action(
        PromptControlActionRequest(
            task_id="explain.v1",
            action_type=PromptControlActionType.PROMOTE_CANDIDATE,
            candidate_prompt_version="foundation.explain.v2",
            requested_by="alice@lotus.test",
            approved_by="bob@lotus.test",
            reason="Approve improved explanation candidate",
        )
    )

    resolved = resolve_runtime_prompt_or_raise("explain.v1")
    history = build_prompt_control_history(task_id="explain.v1")

    assert response.event.action_type == PromptControlActionType.PROMOTE_CANDIDATE
    assert response.rollout_state.active_prompt_version == "foundation.explain.v2"
    assert response.rollout_state.previous_active_prompt_version == "foundation.explain.v1"
    assert response.rollout_state.candidate_prompt_version is None
    assert resolved.prompt.prompt_version == "foundation.explain.v2"
    assert len(history.latest_events) == 1
    assert history.latest_events[0].resulting_active_prompt_version == "foundation.explain.v2"


def test_apply_prompt_control_action_rolls_back_to_previous_active_version() -> None:
    reset_prompt_store_cache()
    apply_prompt_control_action(
        PromptControlActionRequest(
            task_id="explain.v1",
            action_type=PromptControlActionType.PROMOTE_CANDIDATE,
            candidate_prompt_version="foundation.explain.v2",
            requested_by="alice@lotus.test",
            approved_by="bob@lotus.test",
            reason="Approve improved explanation candidate",
        )
    )

    response = apply_prompt_control_action(
        PromptControlActionRequest(
            task_id="explain.v1",
            action_type=PromptControlActionType.ROLLBACK_TO_PREVIOUS_ACTIVE,
            requested_by="alice@lotus.test",
            approved_by="bob@lotus.test",
            reason="Restore known-good prompt",
        )
    )

    resolved = resolve_runtime_prompt_or_raise("explain.v1")

    assert response.rollout_state.active_prompt_version == "foundation.explain.v1"
    assert response.rollout_state.candidate_prompt_version == "foundation.explain.v2"
    assert response.rollout_state.previous_active_prompt_version is None
    assert resolved.prompt.prompt_version == "foundation.explain.v1"


def test_apply_prompt_control_action_rejects_invalid_rollback_without_previous_active() -> None:
    reset_prompt_store_cache()

    try:
        apply_prompt_control_action(
            PromptControlActionRequest(
                task_id="explain.v1",
                action_type=PromptControlActionType.ROLLBACK_TO_PREVIOUS_ACTIVE,
                requested_by="alice@lotus.test",
                approved_by="bob@lotus.test",
                reason="Attempt invalid rollback",
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "has no prior active prompt" in str(exc.detail)
    else:
        raise AssertionError("Expected rollback without previous active to fail")
