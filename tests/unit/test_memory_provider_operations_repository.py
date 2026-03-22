from app.contracts.providers import (
    ProviderFailureCategory,
    ProviderOperationsControlActionType,
    ProviderQuotaScope,
)
from app.repositories.memory_provider_operations_repository import (
    InMemoryProviderOperationsRepository,
)
from app.repositories.provider_operations_repository import (
    ProviderBudgetStateRecord,
    ProviderDegradationStateRecord,
    ProviderOperationsEventRecord,
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
    assert repository.get_quota_state(scope=ProviderQuotaScope.DEFAULT, scope_key="global") is None
    assert repository.get_budget_state(budget_key="missing") is None
    assert repository.get_degradation_state(degradation_key="missing") is None


def test_memory_provider_operations_repository_applies_atomic_mutations() -> None:
    repository = InMemoryProviderOperationsRepository()

    quota = repository.increment_quota_state(
        scope=ProviderQuotaScope.DEFAULT,
        scope_key="global",
        amount=1,
        updated_at="2026-03-23T00:00:00Z",
    )
    budget = repository.add_budget_spend(
        budget_key="live_text_generation",
        amount_usd=0.75,
        updated_at="2026-03-23T00:01:00Z",
    )
    degradation = repository.record_degradation_failure(
        degradation_key="live_text_generation",
        category=ProviderFailureCategory.PROVIDER_TIMEOUT,
        updated_at="2026-03-23T00:02:00Z",
    )
    quota = repository.increment_quota_state(
        scope=ProviderQuotaScope.DEFAULT,
        scope_key="global",
        amount=1,
        updated_at="2026-03-23T00:03:00Z",
    )
    budget = repository.add_budget_spend(
        budget_key="live_text_generation",
        amount_usd=0.25,
        updated_at="2026-03-23T00:04:00Z",
    )
    degradation = repository.record_degradation_failure(
        degradation_key="live_text_generation",
        category=ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR,
        updated_at="2026-03-23T00:05:00Z",
    )

    assert quota.request_count == 2
    assert budget.current_spend_usd == 1.0
    assert degradation.consecutive_failure_count == 2
    assert degradation.timeout_failure_count == 1
    assert degradation.upstream_error_failure_count == 1


def test_memory_provider_operations_repository_records_events_and_resets_state() -> None:
    repository = InMemoryProviderOperationsRepository()

    repository.increment_quota_state(
        scope=ProviderQuotaScope.DEFAULT,
        scope_key="global",
        amount=1,
        updated_at="2026-03-23T00:00:00Z",
    )
    repository.add_budget_spend(
        budget_key="live_text_generation",
        amount_usd=0.75,
        updated_at="2026-03-23T00:01:00Z",
    )
    repository.record_degradation_failure(
        degradation_key="live_text_generation",
        category=ProviderFailureCategory.PROVIDER_TIMEOUT,
        updated_at="2026-03-23T00:02:00Z",
    )
    repository.save_operations_event(
        ProviderOperationsEventRecord(
            event_id="evt-1",
            action_type=ProviderOperationsControlActionType.RESET_ALL_PROVIDER_OPERATIONS,
            scope=None,
            scope_key=None,
            reason="Operator reset after review",
            requested_by="ops.user@lotus",
            approved_by="approver.user@lotus",
            affected_record_count=3,
            recorded_at="2026-03-23T00:03:00Z",
        )
    )

    assert repository.reset_quota_states() == 1
    assert repository.reset_budget_state(budget_key="live_text_generation") == 1
    assert repository.reset_degradation_state(degradation_key="live_text_generation") == 1
    events = repository.list_operations_events(limit=10)

    assert len(events) == 1
    assert events[0].event_id == "evt-1"
    assert (
        events[0].action_type == ProviderOperationsControlActionType.RESET_ALL_PROVIDER_OPERATIONS
    )
    assert repository.list_quota_states() == []
    assert repository.get_budget_state(budget_key="live_text_generation") is None
    assert repository.get_degradation_state(degradation_key="live_text_generation") is None
