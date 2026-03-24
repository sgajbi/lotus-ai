from __future__ import annotations

from app.config import settings
from app.contracts.safety import SafetyRunbookReadinessItem, SafetyRunbookReadinessResponse
from app.services.governance_readiness import summarize_activation_items


def build_safety_runbook_readiness() -> SafetyRunbookReadinessResponse:
    items = [
        SafetyRunbookReadinessItem(
            runbook_id="safety_operational_runbook",
            status="READY",
            required_for_activation=True,
            notes=(
                "The service runbook now documents runtime safety activation review, blocked and "
                "degraded execution handling, and the operator-facing status surfaces required to "
                "review safety rollout posture."
            ),
        ),
        SafetyRunbookReadinessItem(
            runbook_id="safety_rollback_and_degraded_response",
            status="READY",
            required_for_activation=True,
            notes=(
                "The runbook documents how operators review documented-only fallback, blocked "
                "execution, and degraded redaction failures without relying on ad hoc runtime "
                "state resets."
            ),
        ),
        SafetyRunbookReadinessItem(
            runbook_id="safety_incident_review_and_audit_evidence",
            status="READY",
            required_for_activation=True,
            notes=(
                "Safety incident review posture is grounded in persisted audit records, execution "
                "evidence, and runtime-backed evaluation runs rather than process-local state."
            ),
        ),
        SafetyRunbookReadinessItem(
            runbook_id="safety_oncall_and_observability_dashboard_pack",
            status="FOUNDATION_DOCUMENTED",
            required_for_activation=True,
            notes=(
                "Safety rollout review flow and bounded observability endpoints are documented, but "
                "named on-call ownership for blocked, degraded, and redacted task outcomes remains "
                "to be approved."
            ),
        ),
    ]
    required_item_count, completed_required_item_count = summarize_activation_items(items)
    return SafetyRunbookReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        runbook_ready=completed_required_item_count == required_item_count,
        required_item_count=required_item_count,
        completed_required_item_count=completed_required_item_count,
        items=items,
    )
