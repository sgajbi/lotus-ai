from __future__ import annotations

from app.config import settings
from app.contracts.providers import (
    ProviderRunbookReadinessItem,
    ProviderRunbookReadinessResponse,
)
from app.services.governance_readiness import summarize_activation_items
from app.services.provider_rollout_posture import build_provider_rollout_posture


def build_provider_runbook_readiness() -> ProviderRunbookReadinessResponse:
    rollout_posture = build_provider_rollout_posture()
    items = [
        ProviderRunbookReadinessItem(
            runbook_id="provider_operational_runbook",
            status="FOUNDATION_DOCUMENTED",
            required_for_activation=True,
            notes=(
                "Provider operating model is documented at a foundation level, but live-provider "
                f"activation steps are not yet finalized. {rollout_posture.notes}"
            ),
        ),
        ProviderRunbookReadinessItem(
            runbook_id="provider_oncall_and_escalation",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "On-call ownership, vendor escalation path, and incident triage playbooks for "
                "live provider execution must be defined before activation."
            ),
        ),
        ProviderRunbookReadinessItem(
            runbook_id="provider_cost_and_rate_limit_controls",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "Runbooks for provider usage limits, rate-limit incidents, and cost-protection "
                "responses are not yet documented, including how operators review and reset durable quota state safely through the control-plane action surface."
            ),
        ),
        ProviderRunbookReadinessItem(
            runbook_id="provider_spend_anomaly_response",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "Runbooks for soft-budget alerts, hard-budget blocks, and spend-anomaly escalation "
                "are not yet documented, including how durable spend posture is reviewed and recovered safely through the control-plane action surface."
            ),
        ),
        ProviderRunbookReadinessItem(
            runbook_id="provider_incident_response_and_rollback",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "Provider incident response, rollback, and safe reversion procedures for live "
                "execution are not yet documented."
            ),
        ),
        ProviderRunbookReadinessItem(
            runbook_id="provider_degradation_and_circuit_response",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "Runbooks for degraded-upstream operation, circuit-open response, cooldown review, "
                "and safe re-enable procedures are not yet documented, including durable circuit-state recovery through the control-plane action surface."
            ),
        ),
        ProviderRunbookReadinessItem(
            runbook_id="provider_observability_incident_views",
            status="READY",
            required_for_activation=True,
            notes=(
                "Bounded provider observability and incident-evidence summaries are now exposed through "
                "`/platform/observability/provider-summary` and `/platform/observability/incident-summary`; "
                "external dashboards remain a deployment concern rather than an RFC-0013 activation gate."
            ),
        ),
    ]
    required_item_count, completed_required_item_count = summarize_activation_items(items)
    return ProviderRunbookReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        runbook_ready=completed_required_item_count == required_item_count,
        required_item_count=required_item_count,
        completed_required_item_count=completed_required_item_count,
        items=items,
    )
