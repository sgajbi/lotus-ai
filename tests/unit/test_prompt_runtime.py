from fastapi import HTTPException

from app.contracts.prompts import PromptLifecycleStatus
from app.services.prompt_runtime import (
    list_active_runtime_prompts,
    list_registered_prompts,
    resolve_runtime_prompt_or_raise,
)


def test_resolve_runtime_prompt_or_raise_returns_active_prompt_selection() -> None:
    resolved = resolve_runtime_prompt_or_raise("explain.v1")

    assert resolved.prompt.task_id == "explain.v1"
    assert resolved.prompt.prompt_version == "foundation.explain.v1"
    assert resolved.selection.task_id == "explain.v1"
    assert resolved.selection.selected_for_runtime is True
    assert "Foundation-phase runtime selects" in resolved.selection.selection_reason


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
        assert "No registered prompt definition" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException for unknown prompt")
