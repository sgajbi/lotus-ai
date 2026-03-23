from app.config import settings
from app.contracts.prompts import PromptManagementMode
from app.services.prompt_governance import build_prompt_governance_status
from app.services.prompt_store import reset_prompt_store_cache


def test_prompt_governance_uses_memory_management_mode() -> None:
    settings.prompt_store_mode = "memory"
    reset_prompt_store_cache()

    status = build_prompt_governance_status()

    assert status.prompt_store_mode == "memory"
    assert status.management_mode == PromptManagementMode.SEEDED_MEMORY
    assert status.runtime_mutation_enabled is True
    assert status.promotion_write_api_enabled is True
    assert "explicit governed promote and rollback actions" in status.promotion_path
    assert status.control_history_endpoint == "/platform/prompts/control-history"
    assert status.active_prompt_count >= 7
