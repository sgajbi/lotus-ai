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
    durable_runtime_ready = (
        settings.prompt_store_mode == "sqlalchemy"
        and settings.evaluation_runtime_store_mode == "sqlalchemy"
    )
    blocking_findings = [
        (
            "Live prompt activation requires SQL-backed prompt rollout state and SQL-backed "
            "evaluation runtime evidence so promotion and rollback survive restart."
            if not durable_runtime_ready
            else ""
        ),
    ]
    blocking_findings = [item for item in blocking_findings if item]
    activation_path = [
        "Use SQL-backed prompt and evaluation-runtime stores before treating prompt rollout as a restart-safe live control plane.",
        "Keep promote and rollback actions bounded to durable prompt candidates with explicit operator approval metadata.",
        "Require `/platform/prompts/evidence-readiness` to report a passing runtime-backed prompt approval gate before promoting a candidate prompt.",
        "Inspect `/platform/prompts/control-history`, `/platform/prompts/runtime-status`, and prompt-linked audit traces after each prompt control action.",
    ]
    return PromptActivationReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        prompt_store_mode=settings.prompt_store_mode,
        management_mode=management_mode,
        activation_ready=durable_runtime_ready,
        blocking_findings=blocking_findings,
        activation_path=activation_path,
    )
