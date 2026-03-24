from __future__ import annotations

from app.config import settings
from app.contracts.prompts import (
    PromptRunbookReadinessItem,
    PromptRunbookReadinessResponse,
)
from app.services.governance_readiness import summarize_activation_items


def build_prompt_runbook_readiness() -> PromptRunbookReadinessResponse:
    items = [
        PromptRunbookReadinessItem(
            runbook_id="prompt_operational_runbook",
            status="READY",
            required_for_activation=True,
            notes=(
                "Prompt promotion, rollback, incident review, and audit-inspection procedures are "
                "documented in the service operations runbook."
            ),
        ),
        PromptRunbookReadinessItem(
            runbook_id="prompt_change_review_and_approval",
            status="READY",
            required_for_activation=True,
            notes=(
                "Governed prompt control actions require requested-by, approved-by, and operator "
                "reason metadata, and the review flow is now documented."
            ),
        ),
        PromptRunbookReadinessItem(
            runbook_id="prompt_rollback_and_incident_response",
            status="READY",
            required_for_activation=True,
            notes=(
                "Rollback, regression triage, and incident-response procedures for prompt rollout "
                "are documented and aligned with the control-plane action model."
            ),
        ),
        PromptRunbookReadinessItem(
            runbook_id="prompt_observability_and_evidence_pack",
            status="READY",
            required_for_activation=True,
            notes=(
                "Operators can inspect prompt rollout state, control history, approval evidence, "
                "platform runtime posture, and audit traces through documented platform endpoints."
            ),
        ),
    ]
    required_item_count, completed_required_item_count = summarize_activation_items(items)
    return PromptRunbookReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        runbook_ready=True,
        required_item_count=required_item_count,
        completed_required_item_count=completed_required_item_count,
        items=items,
    )
