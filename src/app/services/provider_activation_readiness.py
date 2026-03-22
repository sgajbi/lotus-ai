from __future__ import annotations

from app.config import settings
from app.contracts.providers import (
    ProviderActivationReadinessResponse,
    ProviderBudgetState,
    ProviderCredentialStatus,
    ProviderRolloutState,
)
from app.services.provider_configuration_status import (
    build_text_generation_configuration_status,
)
from app.services.provider_budget_policy import build_provider_budget_policy
from app.services.provider_live_execution_state import build_provider_live_execution_state
from app.services.provider_quota_policy import build_provider_quota_policy
from app.services.provider_rollout_posture import build_provider_rollout_posture


def build_provider_activation_readiness() -> ProviderActivationReadinessResponse:
    configuration = build_text_generation_configuration_status()
    budget_policy = build_provider_budget_policy()
    quota_policy = build_provider_quota_policy()
    rollout_posture = build_provider_rollout_posture()
    live_execution_state = build_provider_live_execution_state()
    blocking_findings = [
        "Embedding provider activation remains blocked until retrieval execution and indexing controls are live.",
    ]
    if configuration.rollout_state == ProviderRolloutState.ALLOWLISTED_DISABLED:
        blocking_findings.append(
            "Live-provider rollout is allowlisted but still intentionally disabled pending later activation slices."
        )
    if not configuration.configuration_valid:
        blocking_findings.extend(configuration.findings)
    if quota_policy.quota_enforced and not quota_policy.configuration_valid:
        blocking_findings.extend(quota_policy.findings)
    if budget_policy.budget_enforced and not budget_policy.configuration_valid:
        blocking_findings.extend(budget_policy.findings)
    elif configuration.credential_status == ProviderCredentialStatus.NOT_CONFIGURED:
        blocking_findings.append(
            "No live-provider credentials are configured for any future allowlisted text-generation path."
        )
    if (
        live_execution_state.live_execution_enabled
        and (not quota_policy.quota_enforced or quota_policy.configuration_valid)
        and (not budget_policy.budget_enforced or budget_policy.configuration_valid)
    ):
        activation_ready = True
    else:
        activation_ready = False
        if live_execution_state.blocking_reason is not None:
            blocking_findings.append(live_execution_state.blocking_reason)
        if budget_policy.budget_state == ProviderBudgetState.HARD_LIMIT_BLOCKED:
            blocking_findings.append(
                "Live-provider hard budget posture is currently blocking further execution."
            )
        blocking_findings.append(rollout_posture.notes)
    activation_path = [
        "Review `/platform/providers` and `/platform/providers/policy` to confirm the provider catalog, adapter kind, runtime mode, and selected execution path match the intended rollout posture.",
        "Review `/platform/providers/quota-policy` to confirm live-provider quota enforcement scope, matching order, and blocking posture before activation expands.",
        "Review `/platform/providers/budget-policy` to confirm live-provider spend posture, soft-limit signaling, and hard-budget blocking semantics before activation expands.",
        "Verify allowlisted rollout configuration and credential posture through `/platform/providers/activation-readiness` before any live mode is considered.",
        "Confirm provider evaluation and failure-mode evidence through `/platform/providers/evidence-readiness`.",
        "Confirm on-call, quota-handling, rollback, and observability readiness through `/platform/providers/runbook-readiness`.",
        "Approve activation only when `/platform/providers/governance-status` and the embedded `provider_governance` block in `/platform/runtime-status` both show the same ready-to-activate posture.",
    ]
    return ProviderActivationReadinessResponse(
        service=settings.service_name,
        version=settings.service_version,
        provider_mode=settings.provider_mode,
        embedding_provider_mode=settings.embedding_provider_mode,
        text_generation_configuration=configuration,
        activation_ready=activation_ready,
        blocking_findings=blocking_findings,
        activation_path=activation_path,
    )
