from __future__ import annotations

from copy import deepcopy

from app.contracts.providers import (
    ProviderFailureCategory,
    ProviderQuotaScope,
)
from app.repositories.provider_operations_repository import (
    ProviderBudgetStateRecord,
    ProviderDegradationStateRecord,
    ProviderOperationsEventRecord,
    ProviderOperationsRepository,
    ProviderQuotaStateRecord,
)


class InMemoryProviderOperationsRepository(ProviderOperationsRepository):
    def __init__(self) -> None:
        self._quota_states: dict[tuple[ProviderQuotaScope, str], ProviderQuotaStateRecord] = {}
        self._budget_states: dict[str, ProviderBudgetStateRecord] = {}
        self._degradation_states: dict[str, ProviderDegradationStateRecord] = {}
        self._event_records: list[ProviderOperationsEventRecord] = []

    def list_quota_states(self) -> list[ProviderQuotaStateRecord]:
        return [
            deepcopy(self._quota_states[key])
            for key in sorted(self._quota_states, key=lambda item: (item[0].value, item[1]))
        ]

    def get_quota_state(
        self,
        *,
        scope: ProviderQuotaScope,
        scope_key: str,
    ) -> ProviderQuotaStateRecord | None:
        record = self._quota_states.get((scope, scope_key))
        if record is None:
            return None
        return deepcopy(record)

    def save_quota_state(self, record: ProviderQuotaStateRecord) -> None:
        self._quota_states[(record.scope, record.scope_key)] = deepcopy(record)

    def increment_quota_state(
        self,
        *,
        scope: ProviderQuotaScope,
        scope_key: str,
        amount: int,
        updated_at: str,
    ) -> ProviderQuotaStateRecord:
        record = self._quota_states.get((scope, scope_key))
        current_count = 0 if record is None else record.request_count
        updated = ProviderQuotaStateRecord(
            scope=scope,
            scope_key=scope_key,
            request_count=current_count + amount,
            updated_at=updated_at,
        )
        self._quota_states[(scope, scope_key)] = deepcopy(updated)
        return deepcopy(updated)

    def get_budget_state(self, *, budget_key: str) -> ProviderBudgetStateRecord | None:
        record = self._budget_states.get(budget_key)
        if record is None:
            return None
        return deepcopy(record)

    def save_budget_state(self, record: ProviderBudgetStateRecord) -> None:
        self._budget_states[record.budget_key] = deepcopy(record)

    def add_budget_spend(
        self,
        *,
        budget_key: str,
        amount_usd: float,
        updated_at: str,
    ) -> ProviderBudgetStateRecord:
        record = self._budget_states.get(budget_key)
        current_spend_usd = 0.0 if record is None else record.current_spend_usd
        updated = ProviderBudgetStateRecord(
            budget_key=budget_key,
            current_spend_usd=round(current_spend_usd + amount_usd, 8),
            updated_at=updated_at,
        )
        self._budget_states[budget_key] = deepcopy(updated)
        return deepcopy(updated)

    def get_degradation_state(
        self,
        *,
        degradation_key: str,
    ) -> ProviderDegradationStateRecord | None:
        record = self._degradation_states.get(degradation_key)
        if record is None:
            return None
        return deepcopy(record)

    def save_degradation_state(self, record: ProviderDegradationStateRecord) -> None:
        self._degradation_states[record.degradation_key] = deepcopy(record)

    def record_degradation_failure(
        self,
        *,
        degradation_key: str,
        category: ProviderFailureCategory,
        updated_at: str,
    ) -> ProviderDegradationStateRecord:
        record = self._degradation_states.get(degradation_key)
        current = (
            ProviderDegradationStateRecord(
                degradation_key=degradation_key,
                consecutive_failure_count=0,
                last_failure_category=None,
                circuit_open_until=None,
                timeout_failure_count=0,
                rate_limited_failure_count=0,
                upstream_error_failure_count=0,
                updated_at=updated_at,
            )
            if record is None
            else record
        )
        updated = ProviderDegradationStateRecord(
            degradation_key=degradation_key,
            consecutive_failure_count=current.consecutive_failure_count + 1,
            last_failure_category=category,
            circuit_open_until=current.circuit_open_until,
            timeout_failure_count=current.timeout_failure_count
            + int(category == ProviderFailureCategory.PROVIDER_TIMEOUT),
            rate_limited_failure_count=current.rate_limited_failure_count
            + int(category == ProviderFailureCategory.PROVIDER_RATE_LIMITED),
            upstream_error_failure_count=current.upstream_error_failure_count
            + int(category == ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR),
            updated_at=updated_at,
        )
        self._degradation_states[degradation_key] = deepcopy(updated)
        return deepcopy(updated)

    def reset_quota_states(
        self,
        *,
        scope: ProviderQuotaScope | None = None,
        scope_key: str | None = None,
    ) -> int:
        keys = [
            key
            for key in self._quota_states
            if (scope is None or key[0] == scope) and (scope_key is None or key[1] == scope_key)
        ]
        for key in keys:
            self._quota_states.pop(key, None)
        return len(keys)

    def reset_budget_state(self, *, budget_key: str) -> int:
        return int(self._budget_states.pop(budget_key, None) is not None)

    def reset_degradation_state(self, *, degradation_key: str) -> int:
        return int(self._degradation_states.pop(degradation_key, None) is not None)

    def save_operations_event(self, record: ProviderOperationsEventRecord) -> None:
        self._event_records.insert(0, deepcopy(record))

    def list_operations_events(self, *, limit: int) -> list[ProviderOperationsEventRecord]:
        return [deepcopy(record) for record in self._event_records[:limit]]
