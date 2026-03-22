from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.contracts.providers import (
    ProviderBudgetPolicyResponse,
    ProviderBudgetState,
    ProviderExecutionResponse,
    ProviderFailureCategory,
)
from app.providers.base import ProviderExecutionError

_CURRENT_SPEND_USD = 0.0


@dataclass(frozen=True)
class ParsedProviderBudgetPolicy:
    budget_enforced: bool
    configuration_valid: bool
    budget_state: ProviderBudgetState
    current_spend_usd: float
    soft_budget_usd: float | None
    hard_budget_usd: float | None
    remaining_budget_usd: float | None
    findings: list[str]
    usage_to_budget_notes: list[str]


def build_provider_budget_policy() -> ProviderBudgetPolicyResponse:
    parsed = parse_provider_budget_policy()
    return ProviderBudgetPolicyResponse(
        service=settings.service_name,
        version=settings.service_version,
        provider_mode=settings.provider_mode,
        budget_enforced=parsed.budget_enforced,
        configuration_valid=parsed.configuration_valid,
        budget_state=parsed.budget_state,
        current_spend_usd=parsed.current_spend_usd,
        soft_budget_usd=parsed.soft_budget_usd,
        hard_budget_usd=parsed.hard_budget_usd,
        remaining_budget_usd=parsed.remaining_budget_usd,
        findings=parsed.findings,
        usage_to_budget_notes=parsed.usage_to_budget_notes,
    )


def parse_provider_budget_policy() -> ParsedProviderBudgetPolicy:
    findings: list[str] = []
    configuration_valid = True
    current_spend_usd = round(_CURRENT_SPEND_USD, 8)
    soft_budget_usd = settings.live_text_soft_budget_usd
    hard_budget_usd = settings.live_text_hard_budget_usd

    if soft_budget_usd is not None and soft_budget_usd <= 0:
        configuration_valid = False
        findings.append("Soft provider budget must be a positive USD value when configured.")
    if hard_budget_usd is not None and hard_budget_usd <= 0:
        configuration_valid = False
        findings.append("Hard provider budget must be a positive USD value when configured.")
    if (
        soft_budget_usd is not None
        and hard_budget_usd is not None
        and soft_budget_usd > hard_budget_usd
    ):
        configuration_valid = False
        findings.append("Soft provider budget must not exceed the hard provider budget.")
    if settings.live_text_budget_enforced and hard_budget_usd is None:
        configuration_valid = False
        findings.append(
            "Live-provider budget enforcement requires a configured hard budget threshold."
        )
    if settings.live_text_budget_enforced and (
        settings.live_text_input_cost_per_1k_tokens is None
        or settings.live_text_output_cost_per_1k_tokens is None
    ):
        configuration_valid = False
        findings.append(
            "Live-provider budget enforcement requires configured input and output token rate-card values."
        )

    remaining_budget_usd = None
    if hard_budget_usd is not None:
        remaining_budget_usd = round(max(hard_budget_usd - current_spend_usd, 0.0), 8)

    budget_state = _resolve_budget_state(
        budget_enforced=settings.live_text_budget_enforced,
        configuration_valid=configuration_valid,
        current_spend_usd=current_spend_usd,
        soft_budget_usd=soft_budget_usd,
        hard_budget_usd=hard_budget_usd,
    )

    if not findings:
        findings.append("Provider budget posture is internally consistent for the current phase.")

    return ParsedProviderBudgetPolicy(
        budget_enforced=settings.live_text_budget_enforced,
        configuration_valid=configuration_valid,
        budget_state=budget_state,
        current_spend_usd=current_spend_usd,
        soft_budget_usd=soft_budget_usd,
        hard_budget_usd=hard_budget_usd,
        remaining_budget_usd=remaining_budget_usd,
        findings=findings,
        usage_to_budget_notes=[
            "Tracked spend is derived only from structured live-provider cost evidence emitted by successful provider responses.",
            "Soft budget posture is advisory and inspectable; hard budget posture is blocking when enforcement is enabled.",
            "Current slice uses deterministic in-process spend accounting so contract semantics are stable before persistent budget tracking is introduced.",
        ],
    )


def enforce_provider_budget() -> None:
    parsed = parse_provider_budget_policy()
    if not parsed.budget_enforced:
        return
    if not parsed.configuration_valid:
        raise ProviderExecutionError(
            category=ProviderFailureCategory.INVALID_BUDGET_CONFIGURATION,
            message="Live-provider budget configuration is invalid and cannot be enforced safely.",
        )
    if parsed.budget_state == ProviderBudgetState.HARD_LIMIT_BLOCKED:
        raise ProviderExecutionError(
            category=ProviderFailureCategory.BUDGET_EXCEEDED,
            message="Live-provider hard budget threshold has been reached.",
        )


def record_provider_spend(response: ProviderExecutionResponse) -> None:
    global _CURRENT_SPEND_USD
    if response.stubbed:
        return
    if response.estimated_cost_usd is None:
        return
    _CURRENT_SPEND_USD = round(_CURRENT_SPEND_USD + response.estimated_cost_usd, 8)


def reset_provider_budget_state() -> None:
    global _CURRENT_SPEND_USD
    _CURRENT_SPEND_USD = 0.0


def _resolve_budget_state(
    *,
    budget_enforced: bool,
    configuration_valid: bool,
    current_spend_usd: float,
    soft_budget_usd: float | None,
    hard_budget_usd: float | None,
) -> ProviderBudgetState:
    if not budget_enforced:
        return ProviderBudgetState.NOT_ENFORCED
    if not configuration_valid:
        return ProviderBudgetState.INVALID
    if hard_budget_usd is not None and current_spend_usd >= hard_budget_usd:
        return ProviderBudgetState.HARD_LIMIT_BLOCKED
    if soft_budget_usd is not None and current_spend_usd >= soft_budget_usd:
        return ProviderBudgetState.SOFT_LIMIT_REACHED
    return ProviderBudgetState.BELOW_SOFT_LIMIT
