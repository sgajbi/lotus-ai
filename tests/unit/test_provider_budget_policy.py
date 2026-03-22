from app.config import settings
from app.contracts.providers import (
    ProviderAdapterKind,
    ProviderBudgetState,
    ProviderExecutionResponse,
)
from app.services.provider_budget_policy import (
    build_provider_budget_policy,
    enforce_provider_budget,
    record_provider_spend,
)
from app.providers.base import ProviderExecutionError


def _response(cost: float | None, *, stubbed: bool = False) -> ProviderExecutionResponse:
    return ProviderExecutionResponse(
        provider_id="text.openai",
        provider_mode="openai",
        adapter_kind=ProviderAdapterKind.OPENAI_LIVE,
        failure_category=None,
        timeout_ms=4000,
        retry_count=0,
        max_output_tokens=512,
        model_id="gpt-5.4",
        provider_request_id="req-budget-1",
        input_tokens=100,
        output_tokens=200,
        total_tokens=300,
        estimated_cost_usd=cost,
        stubbed=stubbed,
        message="live response",
        structured_output={},
    )


def test_provider_budget_policy_reports_disabled_default_posture() -> None:
    response = build_provider_budget_policy()

    assert response.service == "lotus-ai"
    assert response.provider_mode == "disabled"
    assert response.budget_enforced is False
    assert response.configuration_valid is True
    assert response.budget_state == ProviderBudgetState.NOT_ENFORCED
    assert response.current_spend_usd == 0.0
    assert response.remaining_budget_usd is None


def test_provider_budget_policy_reports_soft_limit_after_tracked_spend() -> None:
    settings.live_text_budget_enforced = True
    settings.live_text_input_cost_per_1k_tokens = 0.01
    settings.live_text_output_cost_per_1k_tokens = 0.03
    settings.live_text_soft_budget_usd = 0.5
    settings.live_text_hard_budget_usd = 1.0

    record_provider_spend(_response(0.75))

    response = build_provider_budget_policy()

    assert response.configuration_valid is True
    assert response.budget_state == ProviderBudgetState.SOFT_LIMIT_REACHED
    assert response.current_spend_usd == 0.75
    assert response.remaining_budget_usd == 0.25


def test_provider_budget_policy_rejects_invalid_configuration() -> None:
    settings.live_text_budget_enforced = True
    settings.live_text_soft_budget_usd = 2.0
    settings.live_text_hard_budget_usd = 1.0

    response = build_provider_budget_policy()

    assert response.configuration_valid is False
    assert response.budget_state == ProviderBudgetState.INVALID
    assert any("must not exceed" in finding for finding in response.findings)


def test_provider_budget_policy_blocks_when_hard_limit_is_reached() -> None:
    settings.live_text_budget_enforced = True
    settings.live_text_input_cost_per_1k_tokens = 0.01
    settings.live_text_output_cost_per_1k_tokens = 0.03
    settings.live_text_soft_budget_usd = 0.5
    settings.live_text_hard_budget_usd = 1.0

    record_provider_spend(_response(1.0))

    response = build_provider_budget_policy()
    assert response.budget_state == ProviderBudgetState.HARD_LIMIT_BLOCKED

    try:
        enforce_provider_budget()
    except ProviderExecutionError as exc:
        assert exc.category.value == "BUDGET_EXCEEDED"
    else:
        raise AssertionError("Expected hard-budget enforcement to block execution")
