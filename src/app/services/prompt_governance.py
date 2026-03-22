from __future__ import annotations

from app.config import settings
from app.contracts.prompts import (
    PromptGovernanceStatusResponse,
    PromptLifecycleStatus,
    PromptManagementMode,
)
from app.services.prompt_registry import list_registered_prompts


def build_prompt_governance_status() -> PromptGovernanceStatusResponse:
    prompts = list_registered_prompts()
    management_mode = (
        PromptManagementMode.MIGRATION_MANAGED
        if settings.prompt_store_mode == "sqlalchemy"
        else PromptManagementMode.SEEDED_MEMORY
    )
    active_prompt_count = sum(
        1 for prompt in prompts if prompt.lifecycle_status == PromptLifecycleStatus.ACTIVE
    )
    return PromptGovernanceStatusResponse(
        prompt_store_mode=settings.prompt_store_mode,
        management_mode=management_mode,
        runtime_mutation_enabled=False,
        promotion_write_api_enabled=False,
        promotion_path=(
            "Prompt definitions are promoted through reviewed repository changes and "
            "Alembic-managed persistence updates; runtime mutation APIs remain disabled."
        ),
        active_prompt_count=active_prompt_count,
    )
