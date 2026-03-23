from __future__ import annotations

from app.config import settings
from app.contracts.prompts import (
    PromptGovernanceStatusResponse,
    PromptManagementMode,
)
from app.services.prompt_runtime import summarize_prompt_lifecycle_counts


def build_prompt_governance_status() -> PromptGovernanceStatusResponse:
    lifecycle_counts = summarize_prompt_lifecycle_counts()
    management_mode = (
        PromptManagementMode.MIGRATION_MANAGED
        if settings.prompt_store_mode == "sqlalchemy"
        else PromptManagementMode.SEEDED_MEMORY
    )
    return PromptGovernanceStatusResponse(
        prompt_store_mode=settings.prompt_store_mode,
        management_mode=management_mode,
        runtime_mutation_enabled=False,
        promotion_write_api_enabled=False,
        promotion_path=(
            "Prompt rollout state is now durable and explicit, but active promotion still remains "
            "read-only until a governed live action surface is introduced; runtime mutation APIs "
            "remain disabled."
        ),
        active_prompt_count=lifecycle_counts.active_prompt_count,
    )
