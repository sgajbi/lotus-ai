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
        "Runtime-backed evaluation evidence is not yet enforced as a hard prompt-promotion gate.",
        "Prompt rollout runbook readiness remains incomplete for named approvers, rollback response, and incident handling.",
        "Prompt evidence readiness remains incomplete for regression, audit-traceability, and rollback-proof review.",
        "Prompt activation still requires end-to-end production hardening beyond the bounded control-plane actions now available.",
    ]
    activation_path = [
        "Keep promote and rollback actions bounded to durable prompt candidates with explicit operator approval metadata.",
        "Wire runtime-backed evaluation evidence into prompt promotion and rollback review.",
        "Complete runbook, observability, and incident-response gates for production prompt changes.",
        "Validate end-to-end prompt selection, rollback, and audit behavior before broad live activation.",
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
