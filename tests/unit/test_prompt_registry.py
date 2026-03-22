from fastapi import HTTPException

from app.config import settings
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


def test_get_prompt_or_raise_rejects_unknown_prompt() -> None:
    try:
        get_prompt_or_raise("missing.v1")
    except HTTPException as exc:
        assert exc.status_code == 404
        assert "No registered prompt definition" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException for unknown prompt")


def test_list_registered_prompts_uses_active_prompt_store_mode() -> None:
    settings.prompt_store_mode = "memory"
    reset_prompt_store_cache()

    prompts = list_registered_prompts()

    assert any(prompt.task_id == "knowledge_answer.v1" for prompt in prompts)
