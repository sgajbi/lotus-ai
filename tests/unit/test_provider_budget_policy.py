from pathlib import Path

from app.config import settings
from app.contracts.providers import ProviderBudgetState
from app.services.provider_budget_policy import (
    build_provider_budget_policy,
    enforce_provider_budget,
    record_attempt_spend,
)
from app.services.provider_usage_accounting import AttemptDebit
from app.providers.base import ProviderExecutionError
from app.services.provider_operations_store import reset_provider_operations_store_cache
from app.services.rate_card_store import reset_rate_card_store_cache
from tests.support.migration_runner import upgrade_database_to_head


def _seed_spend(
    amount: float, *, execution_id: str = "exec-budget-test", attempt_index: int = 0
) -> bool:
    return record_attempt_spend(
        execution_id=execution_id,
        candidate_entry_id="text.openai:gpt-5.4",
        provider_id="text.openai",
        model_revision="gpt-5.4",
        attempt_index=attempt_index,
        debit=AttemptDebit(
            amount_usd=amount,
            basis="ACTUAL_USAGE",
            input_tokens=100,
            output_tokens=200,
            rate_card_ref="default-live-text",
        ),
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

    _seed_spend(0.75)

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


def test_provider_budget_policy_rejects_non_positive_budget_values() -> None:
    settings.live_text_budget_enforced = True
    settings.live_text_soft_budget_usd = 0.0
    settings.live_text_hard_budget_usd = -1.0

    response = build_provider_budget_policy()

    assert response.configuration_valid is False
    assert any(
        "Soft provider budget must be a positive USD value" in finding
        for finding in response.findings
    )
    assert any(
        "Hard provider budget must be a positive USD value" in finding
        for finding in response.findings
    )


def test_provider_budget_policy_blocks_when_hard_limit_is_reached() -> None:
    settings.live_text_budget_enforced = True
    settings.live_text_input_cost_per_1k_tokens = 0.01
    settings.live_text_output_cost_per_1k_tokens = 0.03
    settings.live_text_soft_budget_usd = 0.5
    settings.live_text_hard_budget_usd = 1.0

    _seed_spend(1.0)

    response = build_provider_budget_policy()
    assert response.budget_state == ProviderBudgetState.HARD_LIMIT_BLOCKED

    try:
        enforce_provider_budget()
    except ProviderExecutionError as exc:
        assert exc.category.value == "BUDGET_EXCEEDED"
    else:
        raise AssertionError("Expected hard-budget enforcement to block execution")


def test_provider_budget_policy_enforcement_rejects_invalid_configuration() -> None:
    settings.live_text_budget_enforced = True
    settings.live_text_hard_budget_usd = 1.0

    try:
        enforce_provider_budget()
    except ProviderExecutionError as exc:
        assert exc.category.value == "INVALID_BUDGET_CONFIGURATION"
    else:
        raise AssertionError("Expected invalid budget configuration to block execution")


def test_recording_the_same_attempt_identity_twice_debits_once() -> None:
    """Issue #289: the attempt identity makes recording idempotent - a
    crash-and-retry of the recording call can never double-debit."""

    settings.live_text_budget_enforced = True
    settings.live_text_input_cost_per_1k_tokens = 0.01
    settings.live_text_output_cost_per_1k_tokens = 0.03
    settings.live_text_soft_budget_usd = 1.0
    settings.live_text_hard_budget_usd = 2.0

    assert _seed_spend(0.5) is True
    assert _seed_spend(0.5) is False

    response = build_provider_budget_policy()

    assert response.current_spend_usd == 0.5
    assert response.budget_state == ProviderBudgetState.BELOW_SOFT_LIMIT


def test_provider_budget_policy_persists_spend_in_sql_store_across_store_reset(
    tmp_path: Path,
) -> None:
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-provider-budget.db'}"
    settings.live_text_budget_enforced = True
    settings.live_text_input_cost_per_1k_tokens = 0.01
    settings.live_text_output_cost_per_1k_tokens = 0.03
    settings.live_text_soft_budget_usd = 1.0
    settings.live_text_hard_budget_usd = 2.0
    upgrade_database_to_head(settings.database_url)

    _seed_spend(0.75)
    reset_provider_operations_store_cache()
    reset_rate_card_store_cache()

    response = build_provider_budget_policy()

    assert response.current_spend_usd == 0.75
    assert response.budget_state == ProviderBudgetState.BELOW_SOFT_LIMIT


def test_provider_budget_policy_durable_enforcement_blocks_on_persisted_hard_limit(
    tmp_path: Path,
) -> None:
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-provider-budget.db'}"
    settings.live_text_budget_enforced = True
    settings.live_text_input_cost_per_1k_tokens = 0.01
    settings.live_text_output_cost_per_1k_tokens = 0.03
    settings.live_text_soft_budget_usd = 0.5
    settings.live_text_hard_budget_usd = 1.0
    upgrade_database_to_head(settings.database_url)

    _seed_spend(1.0)
    reset_provider_operations_store_cache()
    reset_rate_card_store_cache()

    try:
        enforce_provider_budget()
    except ProviderExecutionError as exc:
        assert exc.category.value == "BUDGET_EXCEEDED"
    else:
        raise AssertionError("Expected persisted hard-budget posture to block execution")
