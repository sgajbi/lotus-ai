from __future__ import annotations

from app.config import settings
from app.contracts.providers import (
    ProviderEvidenceReadinessItem,
    ProviderEvidenceReadinessResponse,
)


def build_provider_evidence_readiness() -> ProviderEvidenceReadinessResponse:
    items = [
        ProviderEvidenceReadinessItem(
            evidence_id="provider_policy_fixture_pack",
            status="FOUNDATION_STAGED",
            required_for_activation=True,
            notes=(
                "Foundation-phase provider policy fixtures exist, but a provider-specific live "
                "activation evidence pack is not yet approved."
            ),
        ),
        ProviderEvidenceReadinessItem(
            evidence_id="provider_regression_run_baseline",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "A governed regression-run baseline proving provider selection, refusal, and "
                "fallback behavior for rollout candidates is not yet recorded."
            ),
        ),
        ProviderEvidenceReadinessItem(
            evidence_id="provider_audit_traceability_pack",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "Activation review evidence linking provider configuration changes to audit, "
                "cost, and execution traces is not yet assembled."
            ),
        ),
        ProviderEvidenceReadinessItem(
            evidence_id="provider_failover_and_rollback_evidence_pack",
            status="NOT_READY",
            required_for_activation=True,
            notes=(
                "Failover, rollback, and provider-incident recovery evidence proving safe "
                "reversion behavior is not yet documented."
            ),
        ),
    ]
    required_items = [item for item in items if item.required_for_activation]
    completed_required_items = [
        item for item in required_items if item.status in {"READY", "ACTIVATED"}
    ]
    return ProviderEvidenceReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        evidence_ready=False,
        required_item_count=len(required_items),
        completed_required_item_count=len(completed_required_items),
        items=items,
    )
