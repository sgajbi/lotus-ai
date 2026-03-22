from __future__ import annotations

from app.config import settings
from app.contracts.prompts import (
    PromptEvidenceReadinessItem,
    PromptEvidenceReadinessResponse,
)
from app.services.governance_readiness import summarize_activation_items


def build_prompt_evidence_readiness() -> PromptEvidenceReadinessResponse:
    items = [
        PromptEvidenceReadinessItem(
            evidence_id="prompt_fixture_coverage_pack",
            status="FOUNDATION_STAGED",
            required_for_activation=True,
            notes=(
                "Foundation-phase prompt-related task fixtures exist, but a prompt-specific rollout "
                "evidence pack is not yet approved for live activation review."
            ),
        ),
        PromptEvidenceReadinessItem(
            evidence_id="prompt_regression_run_baseline",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "A governed regression-run baseline proving prompt selection and output behavior "
                "for rollout candidates is not yet recorded."
            ),
        ),
        PromptEvidenceReadinessItem(
            evidence_id="prompt_audit_traceability_pack",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "Activation review evidence linking prompt changes to audit, approval, and "
                "runtime-selection traces is not yet assembled."
            ),
        ),
        PromptEvidenceReadinessItem(
            evidence_id="prompt_rollback_evidence_pack",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "Rollback-proof evidence for reverting prompt changes and validating restored "
                "runtime behavior is not yet documented."
            ),
        ),
    ]
    required_item_count, completed_required_item_count = summarize_activation_items(items)
    return PromptEvidenceReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        evidence_ready=False,
        required_item_count=required_item_count,
        completed_required_item_count=completed_required_item_count,
        items=items,
    )
