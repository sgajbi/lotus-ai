from fastapi import HTTPException

from app.contracts.prompts import (
    PromptControlActionRequest,
    PromptControlActionType,
    PromptLifecycleStatus,
)
from app.services.prompt_rollout_control import apply_prompt_control_action
from app.services.prompt_runtime import (
    build_prompt_selection_trace,
    list_active_runtime_prompts,
    list_prompt_rollout_descriptors,
    list_registered_prompts,
    resolve_runtime_prompt_or_raise,
    summarize_prompt_lifecycle_counts,
)


def test_resolve_runtime_prompt_or_raise_returns_active_prompt_selection() -> None:
    resolved = resolve_runtime_prompt_or_raise("explain.v1")

    assert resolved.prompt.task_id == "explain.v1"
    assert resolved.prompt.prompt_version == "foundation.explain.v1"
    assert resolved.selection.task_id == "explain.v1"
    assert resolved.selection.selected_for_runtime is True
    assert "governed prompt control actions" in resolved.selection.selection_reason
    assert resolved.selection.rollout_role.value == "ACTIVE"


def test_list_active_runtime_prompts_matches_active_prompt_inventory() -> None:
    active_task_ids = {
        prompt.task_id
        for prompt in list_registered_prompts()
        if prompt.lifecycle_status == PromptLifecycleStatus.ACTIVE
    }

    resolved_task_ids = {resolved.prompt.task_id for resolved in list_active_runtime_prompts()}

    assert resolved_task_ids == active_task_ids


def test_resolve_runtime_prompt_or_raise_rejects_unknown_prompt() -> None:
    try:
        resolve_runtime_prompt_or_raise("missing.v1")
    except HTTPException as exc:
        assert exc.status_code == 404
        assert "No governed prompt rollout state" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException for unknown prompt")


def test_summarize_prompt_lifecycle_counts_matches_registered_inventory() -> None:
    registered_prompts = list_registered_prompts()
    counts = summarize_prompt_lifecycle_counts()

    assert counts.active_prompt_count == sum(
        1
        for prompt in registered_prompts
        if prompt.lifecycle_status == PromptLifecycleStatus.ACTIVE
    )
    assert counts.retired_prompt_count == sum(
        1
        for prompt in registered_prompts
        if prompt.lifecycle_status == PromptLifecycleStatus.RETIRED
    )
    assert counts.candidate_prompt_count == 0


def test_list_prompt_rollout_descriptors_matches_runtime_inventory() -> None:
    rollout_descriptors = list_prompt_rollout_descriptors()

    assert any(descriptor.task_id == "explain.v1" for descriptor in rollout_descriptors)
    assert all(
        descriptor.rollout_mode.value == "GOVERNED_CONTROL_ACTIONS"
        for descriptor in rollout_descriptors
    )
    assert all(descriptor.runtime_mutation_enabled is True for descriptor in rollout_descriptors)
    assert all(descriptor.latest_control_event is None for descriptor in rollout_descriptors)


def test_build_prompt_selection_trace_includes_latest_control_event_after_promotion() -> None:
    apply_prompt_control_action(
        PromptControlActionRequest(
            task_id="explain.v1",
            action_type=PromptControlActionType.PROMOTE_CANDIDATE,
            candidate_prompt_version="foundation.explain.v2",
            requested_by="alice@lotus.test",
            approved_by="bob@lotus.test",
            reason="Promote explanation prompt",
        )
    )

    trace = build_prompt_selection_trace("explain.v1")

    assert trace.prompt_version == "foundation.explain.v2"
    assert trace.previous_active_prompt_version == "foundation.explain.v1"
    assert trace.latest_control_event is not None
    assert trace.latest_control_event.action_type == PromptControlActionType.PROMOTE_CANDIDATE
