from __future__ import annotations

from app.config import settings
from app.contracts.providers import (
    ProviderBudgetState,
    ProviderDegradationStatusDescriptor,
    ProviderOperationsState,
    ProviderOperationsStatusResponse,
)
from app.services.provider_budget_policy import build_provider_budget_policy
from app.services.provider_live_execution_state import build_provider_live_execution_state
from app.services.provider_quota_policy import build_provider_quota_policy


def build_provider_operations_status() -> ProviderOperationsStatusResponse:
    live_execution_state = build_provider_live_execution_state()
    quota_policy = build_provider_quota_policy()
    budget_policy = build_provider_budget_policy()
    degradation_status = _build_provider_degradation_status()

    operations_state, blocking_reasons = _resolve_provider_operations_state(
        live_execution_state=live_execution_state,
        quota_policy=quota_policy,
        budget_policy=budget_policy,
        degradation_status=degradation_status,
    )

    return ProviderOperationsStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        provider_mode=settings.provider_mode,
        operations_state=operations_state,
        runtime_execution_enabled=live_execution_state.live_execution_enabled,
        rollout_blocked=operations_state == ProviderOperationsState.ROLLOUT_BLOCKED,
        quota_policy=quota_policy,
        budget_policy=budget_policy,
        degradation_status=degradation_status,
        blocking_reasons=blocking_reasons,
        summary=_build_provider_operations_summary(
            operations_state=operations_state,
            live_execution_enabled=live_execution_state.live_execution_enabled,
            degradation_status=degradation_status,
        ),
    )


def _build_provider_degradation_status() -> ProviderDegradationStatusDescriptor:
    return ProviderDegradationStatusDescriptor(
        status="DOCUMENTED_ONLY",
        findings=[
            "Provider degradation and circuit-breaker posture remain documented-only until RFC-0004 Slice 4 is implemented."
        ],
    )


def _resolve_provider_operations_state(
    *,
    live_execution_state: object,
    quota_policy: object,
    budget_policy: object,
    degradation_status: ProviderDegradationStatusDescriptor,
) -> tuple[ProviderOperationsState, list[str]]:
    blocking_reasons: list[str] = []

    live_execution_enabled = getattr(live_execution_state, "live_execution_enabled")
    blocking_reason = getattr(live_execution_state, "blocking_reason")
    quota_enforced = getattr(quota_policy, "quota_enforced")
    quota_valid = getattr(quota_policy, "configuration_valid")
    quotas = getattr(quota_policy, "quotas")
    budget_enforced = getattr(budget_policy, "budget_enforced")
    budget_valid = getattr(budget_policy, "configuration_valid")
    budget_state = getattr(budget_policy, "budget_state")

    if not live_execution_enabled:
        if blocking_reason is not None:
            blocking_reasons.append(blocking_reason)
        if quota_enforced and not quota_valid:
            blocking_reasons.extend(getattr(quota_policy, "findings"))
        if budget_enforced and not budget_valid:
            blocking_reasons.extend(getattr(budget_policy, "findings"))
        return (ProviderOperationsState.ROLLOUT_BLOCKED, blocking_reasons)

    if quota_enforced and quotas and any(quota.remaining_request_count == 0 for quota in quotas):
        blocking_reasons.append(
            "At least one configured live-provider quota scope is currently exhausted."
        )
        return (ProviderOperationsState.QUOTA_BLOCKED, blocking_reasons)

    if budget_state == ProviderBudgetState.HARD_LIMIT_BLOCKED:
        blocking_reasons.append(
            "Live-provider hard budget posture is currently blocking further execution."
        )
        return (ProviderOperationsState.BUDGET_BLOCKED, blocking_reasons)

    if budget_state == ProviderBudgetState.SOFT_LIMIT_REACHED:
        blocking_reasons.append(
            "Live-provider spend has reached the configured soft budget threshold."
        )
        return (ProviderOperationsState.BUDGET_SOFT_LIMIT, blocking_reasons)

    if degradation_status.status == "DEGRADED_UPSTREAM":
        blocking_reasons.extend(degradation_status.findings)
        return (ProviderOperationsState.DEGRADED_UPSTREAM, blocking_reasons)

    if degradation_status.status == "CIRCUIT_OPEN":
        blocking_reasons.extend(degradation_status.findings)
        return (ProviderOperationsState.CIRCUIT_OPEN, blocking_reasons)

    return (ProviderOperationsState.NORMAL, blocking_reasons)


def _build_provider_operations_summary(
    *,
    operations_state: ProviderOperationsState,
    live_execution_enabled: bool,
    degradation_status: ProviderDegradationStatusDescriptor,
) -> list[str]:
    return [
        f"Provider operations state is `{operations_state.value}`.",
        (
            "Live-provider execution is currently enabled for at least one allowlisted path."
            if live_execution_enabled
            else "Live-provider execution is currently not enabled; operator posture remains rollout-blocked."
        ),
        (
            "Upstream degradation posture remains documented-only in the current slice."
            if degradation_status.status == "DOCUMENTED_ONLY"
            else "Upstream degradation posture is actively enforced."
        ),
    ]
