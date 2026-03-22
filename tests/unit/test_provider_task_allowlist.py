from app.config import settings
from app.services.provider_task_allowlist import (
    is_live_text_task_allowlisted,
    list_invalid_live_text_allowlisted_task_ids,
    list_live_text_allowlisted_task_ids,
)


def test_live_text_task_allowlist_is_sorted_and_deduplicated() -> None:
    settings.live_text_allowed_task_ids = "summarize.v1, explain.v1, summarize.v1"

    assert list_live_text_allowlisted_task_ids() == ["explain.v1", "summarize.v1"]
    assert is_live_text_task_allowlisted("explain.v1") is True
    assert is_live_text_task_allowlisted("classify.v1") is False


def test_live_text_task_allowlist_rejects_unknown_and_retrieval_backed_tasks() -> None:
    settings.live_text_allowed_task_ids = "unknown.v1, knowledge_answer.v1, explain.v1"

    assert list_invalid_live_text_allowlisted_task_ids() == ["knowledge_answer.v1", "unknown.v1"]
