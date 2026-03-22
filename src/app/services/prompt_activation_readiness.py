from __future__ import annotations

from app.config import settings
from app.contracts.prompts import (
    PromptActivationReadinessResponse,
    PromptManagementMode,
)


def build_prompt_activation_readiness() -> PromptActivationReadinessResponse:
    management_mode = (
        PromptManagementMode.MIGRATION_MANAGED
        if settings.prompt_store_mode == "sqlalchemy"
        else PromptManagementMode.SEEDED_MEMORY
    )
    blocking_findings = [
        "Runtime prompt mutation remains disabled in the current foundation phase.",
        "Prompt promotion write APIs are not enabled for live rollout changes.",
        "Prompt promotion is still governed through reviewed repository changes and migration-managed updates.",
        "No governed live prompt approval and rollback workflow has been activated yet.",
    ]
    activation_path = [
        "Approve a governed prompt rollout model with explicit review, approval, and rollback controls.",
        "Introduce a live promotion path that preserves provenance, auditability, and runtime safety constraints.",
        "Enable prompt rollout changes through a reviewed slice with evaluation evidence and supportability gates.",
        "Validate end-to-end prompt selection and rollback behavior before allowing live promotion changes.",
    ]
    return PromptActivationReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        prompt_store_mode=settings.prompt_store_mode,
        management_mode=management_mode,
        activation_ready=False,
        blocking_findings=blocking_findings,
        activation_path=activation_path,
    )
