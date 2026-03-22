from app.contracts.providers import ProviderFailureCategory, ProviderQuotaScope
from app.repositories.memory_provider_operations_repository import (
    InMemoryProviderOperationsRepository,
)
from app.repositories.provider_operations_repository import (
    ProviderBudgetStateRecord,
    ProviderDegradationStateRecord,
    ProviderQuotaStateRecord,
)


def test_memory_provider_operations_repository_round_trip() -> None:
    repository = InMemoryProviderOperationsRepository()

    repository.save_quota_state(
        ProviderQuotaStateRecord(
            scope=ProviderQuotaScope.CALLER_APP,
            scope_key="lotus-manage",
            request_count=3,
            updated_at="2026-03-23T00:00:00Z",
        )
    )
    repository.save_budget_state(
        ProviderBudgetStateRecord(
            budget_key="live_text_generation",
            current_spend_usd=12.5,
            updated_at="2026-03-23T00:01:00Z",
        )
    )
    repository.save_degradation_state(
        ProviderDegradationStateRecord(
            degradation_key="live_text_generation",
            consecutive_failure_count=2,
            last_failure_category=ProviderFailureCategory.PROVIDER_TIMEOUT,
            circuit_open_until="2026-03-23T00:05:00Z",
            timeout_failure_count=2,
            rate_limited_failure_count=1,
            upstream_error_failure_count=0,
            updated_at="2026-03-23T00:02:00Z",
        )
    )

    quota = repository.get_quota_state(
        scope=ProviderQuotaScope.CALLER_APP,
        scope_key="lotus-manage",
    )
    budget = repository.get_budget_state(budget_key="live_text_generation")
    degradation = repository.get_degradation_state(degradation_key="live_text_generation")

    assert quota is not None
    assert quota.request_count == 3
    assert repository.list_quota_states() == [quota]
    assert budget is not None
    assert budget.current_spend_usd == 12.5
    assert degradation is not None
    assert degradation.last_failure_category == ProviderFailureCategory.PROVIDER_TIMEOUT
    assert degradation.rate_limited_failure_count == 1


def test_memory_provider_operations_repository_returns_none_for_unknown_records() -> None:
    repository = InMemoryProviderOperationsRepository()

    assert repository.list_quota_states() == []
    assert (
        repository.get_quota_state(scope=ProviderQuotaScope.DEFAULT, scope_key="global") is None
    )
    assert repository.get_budget_state(budget_key="missing") is None
    assert repository.get_degradation_state(degradation_key="missing") is None
