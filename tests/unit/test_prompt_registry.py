from app.contracts.prompts import PromptLifecycleStatus, PromptManagementMode
from fastapi import HTTPException

from app.config import settings
from app.prompts.registry import get_prompt_by_task_id
from app.services.prompt_registry import get_prompt_or_raise, list_registered_prompts
from app.services.prompt_store import reset_prompt_store_cache


def test_list_registered_prompts_contains_task_entries() -> None:
    prompts = list_registered_prompts()

    assert len(prompts) >= 7
    assert any(prompt.task_id == "explain.v1" for prompt in prompts)


def test_get_prompt_or_raise_returns_registered_prompt() -> None:
    prompt = get_prompt_or_raise("explain.v1")

    assert prompt.prompt_version == "foundation.explain.v1"
    assert prompt.prompt_kind == "system"
    assert prompt.lifecycle_status == PromptLifecycleStatus.ACTIVE
    assert prompt.management_mode == PromptManagementMode.SEEDED_MEMORY


def test_get_prompt_or_raise_rejects_unknown_prompt() -> None:
    try:
        get_prompt_or_raise("missing.v1")
    except HTTPException as exc:
        assert exc.status_code == 404
        assert "No governed prompt rollout state" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException for unknown prompt")


def test_list_registered_prompts_uses_active_prompt_store_mode() -> None:
    settings.prompt_store_mode = "memory"
    reset_prompt_store_cache()

    prompts = list_registered_prompts()

    assert any(prompt.task_id == "knowledge_answer.v1" for prompt in prompts)
    assert all(prompt.source_reference == "app.prompts.registry:_PROMPTS" for prompt in prompts)


def test_get_prompt_by_task_id_returns_only_active_seeded_prompt() -> None:
    prompt = get_prompt_by_task_id("explain.v1")

    assert prompt is not None
    assert prompt.prompt_version == "foundation.explain.v1"


def test_get_prompt_by_task_id_returns_none_for_unknown_task() -> None:
    assert get_prompt_by_task_id("missing.v1") is None
