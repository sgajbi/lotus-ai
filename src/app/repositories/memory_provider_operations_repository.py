from __future__ import annotations

from collections.abc import Sequence

from copy import deepcopy

from app.contracts.providers import (
    ProviderFailureCategory,
    ProviderQuotaScope,
)
from app.contracts.governed_actions import GovernedActionRecord, GovernedActionStatus
from app.repositories.provider_operations_repository import (
    ProviderAttemptDebitRecord,
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
        self._governed_actions: dict[str, GovernedActionRecord] = {}
        self._attempt_debits: dict[str, ProviderAttemptDebitRecord] = {}

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

    def record_attempt_debit(self, record: ProviderAttemptDebitRecord, *, budget_key: str) -> bool:
        if record.debit_id in self._attempt_debits:
            return False
        self._attempt_debits[record.debit_id] = deepcopy(record)
        self.add_budget_spend(
            budget_key=budget_key,
            amount_usd=record.amount_usd,
            updated_at=record.recorded_at,
        )
        return True

    def list_attempt_debits(self, *, limit: int = 100) -> Sequence[ProviderAttemptDebitRecord]:
        records = sorted(
            self._attempt_debits.values(),
            key=lambda item: (item.recorded_at, item.debit_id),
            reverse=True,
        )
        return [deepcopy(record) for record in records[: max(limit, 0)]]

    def delete_attempt_debits(self, debit_ids: Sequence[str]) -> int:
        deleted = 0
        for debit_id in debit_ids:
            if self._attempt_debits.pop(debit_id, None) is not None:
                deleted += 1
        return deleted

    def sum_attempt_debits(self, *, debit_id_prefix: str) -> float:
        return round(
            sum(
                record.amount_usd
                for debit_id, record in self._attempt_debits.items()
                if debit_id.startswith(debit_id_prefix)
            ),
            8,
        )

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

    def reset_degradation_states(self) -> int:
        affected = len(self._degradation_states)
        self._degradation_states.clear()
        return affected

    def save_operations_event(self, record: ProviderOperationsEventRecord) -> None:
        self._event_records.insert(0, deepcopy(record))

    def list_operations_events(self, *, limit: int) -> list[ProviderOperationsEventRecord]:
        return [deepcopy(record) for record in self._event_records[:limit]]

    def delete_operations_events(self, event_ids: Sequence[str]) -> int:
        wanted = set(event_ids)
        before = len(self._event_records)
        self._event_records = [r for r in self._event_records if r.event_id not in wanted]
        return before - len(self._event_records)

    def delete_governed_actions(self, action_ids: Sequence[str]) -> int:
        deleted = 0
        for action_id in action_ids:
            if self._governed_actions.pop(action_id, None) is not None:
                deleted += 1
        return deleted

    def get_governed_action(self, action_id: str) -> GovernedActionRecord | None:
        record = self._governed_actions.get(action_id)
        return record.model_copy(deep=True) if record is not None else None

    def get_pending_governed_action(
        self,
        *,
        action_type: str,
        target: str,
    ) -> GovernedActionRecord | None:
        for record in self._governed_actions.values():
            if (
                record.action_type.value == action_type
                and record.target == target
                and record.status is GovernedActionStatus.PENDING
            ):
                return record.model_copy(deep=True)
        return None

    def list_governed_actions(
        self,
        *,
        status: str | None,
        target: str | None,
        limit: int,
    ) -> list[GovernedActionRecord]:
        records = [
            record
            for record in self._governed_actions.values()
            if (status is None or record.status.value == status)
            and (target is None or record.target == target)
        ]
        records.sort(key=lambda record: record.requested_at, reverse=True)
        return [record.model_copy(deep=True) for record in records[:limit]]

    def upsert_governed_action(self, record: GovernedActionRecord) -> None:
        self._governed_actions[record.action_id] = record.model_copy(deep=True)
