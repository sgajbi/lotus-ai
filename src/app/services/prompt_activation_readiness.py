from __future__ import annotations

from app.config import settings
from app.contracts.prompts import (
    PromptActivationReadinessResponse,
    PromptManagementMode,
)
from app.services.prompt_evidence_readiness import build_prompt_evidence_readiness


def build_prompt_activation_readiness() -> PromptActivationReadinessResponse:
    evidence_readiness = build_prompt_evidence_readiness()
    management_mode = (
        PromptManagementMode.MIGRATION_MANAGED
        if settings.prompt_store_mode == "sqlalchemy"
        else PromptManagementMode.SEEDED_MEMORY
    )
    blocking_findings = [
        (
            "Runtime-backed prompt approval evidence is not yet in a passing state and therefore "
            "cannot satisfy governed prompt promotion."
            if not evidence_readiness.approval_gate.approval_ready
            else ""
        ),
        "Prompt rollout runbook readiness remains incomplete for named approvers, rollback response, and incident handling.",
        "Prompt evidence readiness remains incomplete for full production promotion and rollback review.",
        "Prompt activation still requires end-to-end production hardening beyond the bounded control-plane actions now available.",
    ]
    blocking_findings = [item for item in blocking_findings if item]
    activation_path = [
        "Keep promote and rollback actions bounded to durable prompt candidates with explicit operator approval metadata.",
        "Require `/platform/prompts/evidence-readiness` to report a passing runtime-backed prompt approval gate before promoting a candidate prompt.",
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
