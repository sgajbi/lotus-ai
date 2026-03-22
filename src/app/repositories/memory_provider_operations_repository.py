from __future__ import annotations

from copy import deepcopy

from app.contracts.providers import ProviderQuotaScope
from app.repositories.provider_operations_repository import (
    ProviderBudgetStateRecord,
    ProviderDegradationStateRecord,
    ProviderOperationsRepository,
    ProviderQuotaStateRecord,
)


class InMemoryProviderOperationsRepository(ProviderOperationsRepository):
    def __init__(self) -> None:
        self._quota_states: dict[tuple[ProviderQuotaScope, str], ProviderQuotaStateRecord] = {}
        self._budget_states: dict[str, ProviderBudgetStateRecord] = {}
        self._degradation_states: dict[str, ProviderDegradationStateRecord] = {}

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

    def get_budget_state(self, *, budget_key: str) -> ProviderBudgetStateRecord | None:
        record = self._budget_states.get(budget_key)
        if record is None:
            return None
        return deepcopy(record)

    def save_budget_state(self, record: ProviderBudgetStateRecord) -> None:
        self._budget_states[record.budget_key] = deepcopy(record)

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
