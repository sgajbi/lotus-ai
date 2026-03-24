from __future__ import annotations

from app.config import settings
from app.contracts.use_cases import (
    FirstUseCaseRunbookReadinessItem,
    FirstUseCaseRunbookReadinessResponse,
)
from app.services.governance_readiness import summarize_activation_items

_FIRST_USE_CASE_ID = "lotus_performance.analytics_commentary.v1"
_FIRST_USE_CASE_CALLER_APP = "lotus-performance"


def build_first_use_case_runbook_readiness() -> FirstUseCaseRunbookReadinessResponse:
    items = [
        FirstUseCaseRunbookReadinessItem(
            runbook_id="lotus_performance_shared_ownership",
            status="READY",
            required_for_activation=True,
            notes="The integration and use-case guides now define lotus-performance ownership of analytics truth and lotus-ai ownership of explanation generation, audit, and support review posture.",
        ),
        FirstUseCaseRunbookReadinessItem(
            runbook_id="lotus_performance_rollout_and_rollback_review",
            status="READY",
            required_for_activation=True,
            notes="The service runbook now documents limited-rollout review, rollback-to-blocked posture, and the requirement to stop downstream exposure when first-use-case governance is no longer ready.",
        ),
        FirstUseCaseRunbookReadinessItem(
            runbook_id="lotus_performance_support_and_incident_review",
            status="READY",
            required_for_activation=True,
            notes="Operators now have an explicit first-use-case path for inspecting runtime readiness, audit traces, observability incident summaries, and bounded artifact descriptors when commentary or input-shape incidents occur.",
        ),
        FirstUseCaseRunbookReadinessItem(
            runbook_id="lotus_performance_unsupported_input_triage",
            status="READY",
            required_for_activation=True,
            notes="Unsupported or incomplete analytics inputs are now treated as a distinct support and rollback review path rather than normal explanation variance.",
        ),
    ]
    required_item_count, completed_required_item_count = summarize_activation_items(items)
    return FirstUseCaseRunbookReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        use_case_id=_FIRST_USE_CASE_ID,
        downstream_app=_FIRST_USE_CASE_CALLER_APP,
        runbook_ready=required_item_count == completed_required_item_count,
        required_item_count=required_item_count,
        completed_required_item_count=completed_required_item_count,
        items=items,
    )
