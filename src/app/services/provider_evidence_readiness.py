from __future__ import annotations

from app.config import settings
from app.contracts.providers import (
    ProviderEvidenceReadinessItem,
    ProviderEvidenceReadinessResponse,
)
from app.services.governance_readiness import summarize_activation_items
from app.services.provider_evidence_inventory import build_provider_evidence_inventory

_PROVIDER_POLICY_FIXTURE_IDS = frozenset({"provider_policy_examples"})
_PROVIDER_RUNTIME_FIXTURE_IDS = frozenset({"provider_runtime_examples"})
_PROVIDER_FAILURE_FIXTURE_IDS = frozenset({"provider_failure_mode_examples"})
_PROVIDER_RECORDED_BASELINE_FIXTURE_IDS = (
    _PROVIDER_POLICY_FIXTURE_IDS | _PROVIDER_RUNTIME_FIXTURE_IDS | _PROVIDER_FAILURE_FIXTURE_IDS
)


def build_provider_evidence_readiness() -> ProviderEvidenceReadinessResponse:
    inventory = build_provider_evidence_inventory()
    policy_fixture_ready = _PROVIDER_POLICY_FIXTURE_IDS.issubset(inventory.staged_fixture_ids)
    runtime_fixture_ready = _PROVIDER_RUNTIME_FIXTURE_IDS.issubset(inventory.staged_fixture_ids)
    failure_fixture_ready = _PROVIDER_FAILURE_FIXTURE_IDS.issubset(inventory.staged_fixture_ids)
    regression_baseline_ready = _PROVIDER_RECORDED_BASELINE_FIXTURE_IDS.issubset(
        inventory.recorded_provider_fixture_ids
    )
    audit_traceability_staged = "provider_resolution" in inventory.evidence_category_ids

    items = [
        ProviderEvidenceReadinessItem(
            evidence_id="provider_policy_fixture_pack",
            status="READY" if policy_fixture_ready else "NOT_READY",
            required_for_activation=True,
            notes=(
                "Provider policy fixtures cover bounded mode selection and disabled live-provider "
                "rejection behavior."
                if policy_fixture_ready
                else "Provider policy fixtures are not yet staged in the governed eval manifest."
            ),
        ),
        ProviderEvidenceReadinessItem(
            evidence_id="provider_runtime_fixture_pack",
            status="READY" if runtime_fixture_ready else "NOT_READY",
            required_for_activation=True,
            notes=(
                "Provider runtime fixtures cover success-path control preservation and explicit "
                "live-provider rejection posture."
                if runtime_fixture_ready
                else "Provider runtime success and rejection fixtures are not yet staged."
            ),
        ),
        ProviderEvidenceReadinessItem(
            evidence_id="provider_failure_mode_fixture_pack",
            status="READY" if failure_fixture_ready else "NOT_READY",
            required_for_activation=True,
            notes=(
                "Provider failure-mode fixtures cover timeout-budget evidence and explicit "
                "fallback-or-rejection behavior."
                if failure_fixture_ready
                else "Provider timeout and fallback failure-mode fixtures are not yet staged."
            ),
        ),
        ProviderEvidenceReadinessItem(
            evidence_id="provider_regression_run_baseline",
            status="READY" if regression_baseline_ready else "NOT_READY",
            required_for_activation=True,
            notes=(
                "A recorded evaluation run proves provider policy, runtime, and failure-mode "
                f"coverage in '{inventory.latest_recorded_provider_run_id}'."
                if regression_baseline_ready and inventory.latest_recorded_provider_run_id
                else "A governed recorded run proving provider policy, runtime, and failure-mode "
                "coverage is not yet present."
            ),
        ),
        ProviderEvidenceReadinessItem(
            evidence_id="provider_audit_traceability_pack",
            status="FOUNDATION_STAGED" if audit_traceability_staged else "NOT_READY",
            required_for_activation=True,
            notes=(
                "Provider-resolution evidence is emitted in foundation phase, but a live-provider "
                "audit traceability pack linking credentials, cost, and execution review is not "
                "yet approved."
                if audit_traceability_staged
                else "Provider-resolution evidence categories are not yet staged."
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
    required_item_count, completed_required_item_count = summarize_activation_items(items)
    return ProviderEvidenceReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        evidence_ready=False,
        required_item_count=required_item_count,
        completed_required_item_count=completed_required_item_count,
        items=items,
    )
