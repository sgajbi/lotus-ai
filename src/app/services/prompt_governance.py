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
    runtime_mutation_enabled = settings.prompt_store_mode == "sqlalchemy"
    promotion_write_api_enabled = (
        settings.prompt_store_mode == "sqlalchemy"
        and settings.evaluation_runtime_store_mode == "sqlalchemy"
    )
    return PromptGovernanceStatusResponse(
        prompt_store_mode=settings.prompt_store_mode,
        management_mode=management_mode,
        runtime_mutation_enabled=runtime_mutation_enabled,
        promotion_write_api_enabled=promotion_write_api_enabled,
        promotion_path=(
            "Prompt rollout changes flow through explicit governed promote and rollback actions with durable history when SQL-backed prompt rollout state is active; prompt-body editing still remains repository-managed."
        ),
        active_prompt_count=lifecycle_counts.active_prompt_count,
        control_history_endpoint="/platform/prompts/control-history",
    )
