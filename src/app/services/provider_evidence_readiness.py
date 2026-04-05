from __future__ import annotations

from app.config import settings
from app.contracts.providers import (
    ProviderEvidenceReadinessItem,
    ProviderEvidenceReadinessResponse,
)
from app.services.eval_approval_gate_summary import build_provider_approval_gate_summary
from app.services.governance_readiness import summarize_activation_items
from app.services.provider_evidence_inventory import build_provider_evidence_inventory

_PROVIDER_POLICY_FIXTURE_IDS = frozenset({"provider_policy_examples"})
_PROVIDER_RUNTIME_FIXTURE_IDS = frozenset({"provider_runtime_examples"})
_PROVIDER_FAILURE_FIXTURE_IDS = frozenset({"provider_failure_mode_examples"})
_PROVIDER_OPERATIONS_FIXTURE_IDS = frozenset({"provider_operations_examples"})
_PROVIDER_DEGRADATION_FIXTURE_IDS = frozenset({"provider_degradation_examples"})
_PROVIDER_EMBEDDING_FIXTURE_IDS = frozenset({"provider_embedding_examples"})
_PROVIDER_RECORDED_BASELINE_FIXTURE_IDS = (
    _PROVIDER_POLICY_FIXTURE_IDS
    | _PROVIDER_RUNTIME_FIXTURE_IDS
    | _PROVIDER_FAILURE_FIXTURE_IDS
    | _PROVIDER_OPERATIONS_FIXTURE_IDS
    | _PROVIDER_DEGRADATION_FIXTURE_IDS
    | _PROVIDER_EMBEDDING_FIXTURE_IDS
)


def build_provider_evidence_readiness() -> ProviderEvidenceReadinessResponse:
    inventory = build_provider_evidence_inventory()
    approval_gate = build_provider_approval_gate_summary()
    policy_fixture_ready = _PROVIDER_POLICY_FIXTURE_IDS.issubset(inventory.staged_fixture_ids)
    runtime_fixture_ready = _PROVIDER_RUNTIME_FIXTURE_IDS.issubset(inventory.staged_fixture_ids)
    failure_fixture_ready = _PROVIDER_FAILURE_FIXTURE_IDS.issubset(inventory.staged_fixture_ids)
    operations_fixture_ready = _PROVIDER_OPERATIONS_FIXTURE_IDS.issubset(
        inventory.staged_fixture_ids
    )
    degradation_fixture_ready = _PROVIDER_DEGRADATION_FIXTURE_IDS.issubset(
        inventory.staged_fixture_ids
    )
    embedding_fixture_ready = _PROVIDER_EMBEDDING_FIXTURE_IDS.issubset(inventory.staged_fixture_ids)
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
                "Provider runtime fixtures cover stub and local live-provider success posture, "
                "preserved bounded controls, and explicit provider-identity evidence."
                if runtime_fixture_ready
                else "Provider runtime success and rejection fixtures are not yet staged."
            ),
        ),
        ProviderEvidenceReadinessItem(
            evidence_id="provider_failure_mode_fixture_pack",
            status="READY" if failure_fixture_ready else "NOT_READY",
            required_for_activation=True,
            notes=(
                "Provider failure-mode fixtures cover timeout-budget evidence, explicit "
                "fallback-or-rejection behavior, and local unavailable-model, timeout, and malformed-response mapping."
                if failure_fixture_ready
                else "Provider timeout and fallback failure-mode fixtures are not yet staged."
            ),
        ),
        ProviderEvidenceReadinessItem(
            evidence_id="provider_operations_fixture_pack",
            status="READY" if operations_fixture_ready else "NOT_READY",
            required_for_activation=True,
            notes=(
                "Provider operations fixtures cover quota-blocked, hard-budget-blocked, and durable budget restart-survival posture."
                if operations_fixture_ready
                else "Provider quota and budget operations fixtures are not yet staged."
            ),
        ),
        ProviderEvidenceReadinessItem(
            evidence_id="provider_degradation_fixture_pack",
            status="READY" if degradation_fixture_ready else "NOT_READY",
            required_for_activation=True,
            notes=(
                "Provider degradation fixtures cover degraded-upstream, circuit-open, and durable cooldown recovery posture."
                if degradation_fixture_ready
                else "Provider degraded-upstream and circuit-open fixtures are not yet staged."
            ),
        ),
        ProviderEvidenceReadinessItem(
            evidence_id="provider_embedding_fixture_pack",
            status="READY" if embedding_fixture_ready else "NOT_READY",
            required_for_activation=True,
            notes=(
                "Provider embedding fixtures cover bounded live embedding configuration, rejection posture, and successful vector metadata preservation."
                if embedding_fixture_ready
                else "Provider embedding execution fixtures are not yet staged."
            ),
        ),
        ProviderEvidenceReadinessItem(
            evidence_id="provider_regression_run_baseline",
            status="READY" if regression_baseline_ready else "NOT_READY",
            required_for_activation=True,
            notes=(
                "A recorded evaluation run proves provider policy, local and managed runtime parity, failure-mode handling, and durable provider-operations "
                f"coverage in '{inventory.latest_recorded_provider_run_id}'."
                if regression_baseline_ready and inventory.latest_recorded_provider_run_id
                else "A governed recorded run proving provider policy, runtime, failure-mode, durable provider-operations, and embedding coverage is not yet present."
            ),
        ),
        ProviderEvidenceReadinessItem(
            evidence_id="provider_audit_traceability_pack",
            status="FOUNDATION_STAGED" if audit_traceability_staged else "NOT_READY",
            required_for_activation=True,
            notes=(
                "Provider-resolution evidence is emitted in foundation phase, but a live-provider "
                "audit traceability pack linking credentials, cost, quota, budget, and degradation "
                "review is not yet approved."
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
        approval_gate=approval_gate,
    )
