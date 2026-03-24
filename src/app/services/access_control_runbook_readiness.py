from __future__ import annotations

from app.config import settings
from app.contracts.access_control import (
    AccessControlRunbookReadinessItem,
    AccessControlRunbookReadinessResponse,
)
from app.services.governance_readiness import summarize_activation_items


def build_access_control_runbook_readiness() -> AccessControlRunbookReadinessResponse:
    items = [
        AccessControlRunbookReadinessItem(
            runbook_id="caller_onboarding_procedure",
            status="READY",
            required_for_activation=True,
            notes="Caller onboarding and policy review procedures are documented for the caller policy registry.",
        ),
        AccessControlRunbookReadinessItem(
            runbook_id="caller_revocation_procedure",
            status="READY",
            required_for_activation=True,
            notes="Caller disablement and access revocation procedures are documented and aligned with fail-closed enforcement.",
        ),
        AccessControlRunbookReadinessItem(
            runbook_id="tenant_restriction_change_procedure",
            status="READY",
            required_for_activation=True,
            notes="Tenant restriction changes are documented as explicit policy updates that require review before rollout.",
        ),
        AccessControlRunbookReadinessItem(
            runbook_id="blocked_authorization_incident_review",
            status="READY",
            required_for_activation=True,
            notes="Operator guidance covers blocked authorization review using audit records, execution evidence, and control-plane history.",
        ),
        AccessControlRunbookReadinessItem(
            runbook_id="emergency_override_posture",
            status="READY",
            required_for_activation=True,
            notes="No emergency override API exists in RFC-0012; the fail-closed posture is documented explicitly so operators do not assume a hidden bypass exists.",
        ),
    ]
    required_item_count, completed_required_item_count = summarize_activation_items(items)
    return AccessControlRunbookReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        runbook_ready=required_item_count == completed_required_item_count,
        required_item_count=required_item_count,
        completed_required_item_count=completed_required_item_count,
        items=items,
    )
