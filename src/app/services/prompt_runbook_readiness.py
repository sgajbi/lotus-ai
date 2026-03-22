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
            status="FOUNDATION_DOCUMENTED",
            required_for_activation=True,
            notes=(
                "Prompt operating model is documented at a foundation level, but live prompt "
                "promotion and rollback procedures are not yet finalized."
            ),
        ),
        PromptRunbookReadinessItem(
            runbook_id="prompt_change_review_and_approval",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "Named approvers, separation-of-duties rules, and emergency review procedures "
                "for live prompt changes must be defined before activation."
            ),
        ),
        PromptRunbookReadinessItem(
            runbook_id="prompt_rollback_and_incident_response",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "Rollback, incident response, and prompt-regression triage procedures for "
                "live prompt changes are not yet documented."
            ),
        ),
        PromptRunbookReadinessItem(
            runbook_id="prompt_observability_and_evidence_pack",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "Dedicated prompt rollout dashboards, approval evidence views, and audit "
                "inspection procedures must be defined before activation."
            ),
        ),
    ]
    required_item_count, completed_required_item_count = summarize_activation_items(items)
    return PromptRunbookReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        runbook_ready=False,
        required_item_count=required_item_count,
        completed_required_item_count=completed_required_item_count,
        items=items,
    )
