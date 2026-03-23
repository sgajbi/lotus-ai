from app.contracts.prompts import PromptSelectionMode
from app.services.prompt_status import build_prompt_runtime_status


def test_prompt_runtime_status_reports_active_runtime_selections() -> None:
    status = build_prompt_runtime_status()

    assert status.service == "lotus-ai"
    assert status.prompt_store_mode == "memory"
    assert status.selection_mode == PromptSelectionMode.STATIC_ACTIVE
    assert status.rollout_mode.value == "GOVERNED_STATE_READ_ONLY"
    assert status.active_prompt_count >= 7
    assert status.retired_prompt_count == 0
    assert status.candidate_prompt_count == 0
    assert any(selection.task_id == "explain.v1" for selection in status.selections)
    assert all(selection.selected_for_runtime is True for selection in status.selections)
    assert any(state.task_id == "explain.v1" for state in status.rollout_states)
