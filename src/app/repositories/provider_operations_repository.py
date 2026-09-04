from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence
from typing import Protocol

from app.contracts.access_control import AuthorizationDecision
from app.contracts.governed_actions import GovernedActionRecord
from app.contracts.providers import (
    ProviderFailureCategory,
    ProviderQuotaScope,
)
from app.contracts.provider_operations import ProviderOperationsControlActionType


@dataclass(frozen=True)
class ProviderQuotaStateRecord:
    scope: ProviderQuotaScope
    scope_key: str
    request_count: int
    updated_at: str


@dataclass(frozen=True)
class ProviderBudgetStateRecord:
    budget_key: str
    current_spend_usd: float
    updated_at: str


@dataclass(frozen=True)
class ProviderAttemptDebitRecord:
    """One durable economic debit at a provider attempt boundary (issue #289).

    The debit_id is the idempotent attempt identity
    (``adbt:<execution_id>:<provider_id>:<attempt_index>``): recording the
    same identity twice is a no-op, so a crash-and-retry of the recording
    call can never double-debit, and a process death after the attempt
    loses nothing - the debit is already durable.
    """

    debit_id: str
    provider_id: str
    basis: str
    amount_usd: float
    input_tokens: int | None
    output_tokens: int | None
    rate_card_ref: str
    recorded_at: str


@dataclass(frozen=True)
class ProviderDegradationStateRecord:
    degradation_key: str
    consecutive_failure_count: int
    last_failure_category: ProviderFailureCategory | None
    circuit_open_until: str | None
    timeout_failure_count: int
    rate_limited_failure_count: int
    upstream_error_failure_count: int
    updated_at: str


@dataclass(frozen=True)
class ProviderOperationsEventRecord:
    event_id: str
    action_type: ProviderOperationsControlActionType
    scope: ProviderQuotaScope | None
    scope_key: str | None
    reason: str
    requested_by: str
    approved_by: str
    affected_record_count: int
    authorization: AuthorizationDecision
    recorded_at: str


class ProviderOperationsRepository(Protocol):
    def list_quota_states(self) -> list[ProviderQuotaStateRecord]:
        """List all persisted provider quota state records."""

    def get_quota_state(
        self,
        *,
        scope: ProviderQuotaScope,
        scope_key: str,
    ) -> ProviderQuotaStateRecord | None:
        """Fetch one persisted provider quota state record."""

    def save_quota_state(self, record: ProviderQuotaStateRecord) -> None:
        """Persist one provider quota state record."""

    def increment_quota_state(
        self,
        *,
        scope: ProviderQuotaScope,
        scope_key: str,
        amount: int,
        updated_at: str,
    ) -> ProviderQuotaStateRecord:
        """Atomically increment one provider quota state record and return the updated value."""

    def get_budget_state(self, *, budget_key: str) -> ProviderBudgetStateRecord | None:
        """Fetch one persisted provider budget state record."""

    def save_budget_state(self, record: ProviderBudgetStateRecord) -> None:
        """Persist one provider budget state record."""

    def add_budget_spend(
        self,
        *,
        budget_key: str,
        amount_usd: float,
        updated_at: str,
    ) -> ProviderBudgetStateRecord:
        """Atomically add spend to one provider budget state record and return the updated value."""

    def record_attempt_debit(self, record: ProviderAttemptDebitRecord, *, budget_key: str) -> bool:
        """Durably record one attempt debit and advance the budget counter
        together (issue #289). Returns False - a complete no-op, counter
        untouched - when the debit identity is already recorded."""

    def list_attempt_debits(self, *, limit: int = 100) -> Sequence[ProviderAttemptDebitRecord]:
        """Attempt-debit evidence, newest first."""

    def sum_attempt_debits(self, *, debit_id_prefix: str) -> float:
        """Total recorded spend across one execution's debit identities
        (issue #290): the same durable rows that moved the envelope also
        answer 'how much of the caller's ceiling is already consumed'."""

    def delete_attempt_debits(self, debit_ids: Sequence[str]) -> int:
        """Delete attempt-debit evidence rows for the lifecycle engine
        (control-plane evidence family). Deleting evidence never reverses
        the budget counter - the spend already happened."""

    def get_degradation_state(
        self,
        *,
        degradation_key: str,
    ) -> ProviderDegradationStateRecord | None:
        """Fetch one persisted provider degradation state record."""

    def save_degradation_state(self, record: ProviderDegradationStateRecord) -> None:
        """Persist one provider degradation state record."""

    def record_degradation_failure(
        self,
        *,
        degradation_key: str,
        category: ProviderFailureCategory,
        updated_at: str,
    ) -> ProviderDegradationStateRecord:
        """Atomically persist one tracked provider failure and return the updated degradation state."""

    def reset_quota_states(
        self,
        *,
        scope: ProviderQuotaScope | None = None,
        scope_key: str | None = None,
    ) -> int:
        """Reset quota state records and return the number of affected rows."""

    def reset_budget_state(self, *, budget_key: str) -> int:
        """Reset one budget state record and return the number of affected rows."""

    def reset_degradation_state(self, *, degradation_key: str) -> int:
        """Reset one degradation state record and return the number of affected rows."""

    def reset_degradation_states(self) -> int:
        """Reset every degradation state record and return the number of affected rows."""

    def save_operations_event(self, record: ProviderOperationsEventRecord) -> None:
        """Persist one provider-operations control event record."""

    def get_governed_action(self, action_id: str) -> GovernedActionRecord | None:
        """Fetch one governed-action evidence record (issue #157)."""

    def get_pending_governed_action(
        self,
        *,
        action_type: str,
        target: str,
    ) -> GovernedActionRecord | None:
        """Fetch the pending governed action for one action type and target, if any."""

    def upsert_governed_action(self, record: GovernedActionRecord) -> None:
        """Persist one governed-action record by action id."""

    def list_governed_actions(
        self,
        *,
        status: str | None,
        target: str | None,
        limit: int,
    ) -> list[GovernedActionRecord]:
        """List governed-action evidence records, newest requested first."""

    def delete_operations_events(self, event_ids: Sequence[str]) -> int:
        """Delete operations events by id for the lifecycle engine (issue #158, S2b)."""

    def delete_governed_actions(self, action_ids: Sequence[str]) -> int:
        """Delete non-current governed-action evidence by id (issue #158, S2b)."""

    def list_operations_events(self, *, limit: int) -> list[ProviderOperationsEventRecord]:
        """List most recent provider-operations control event records."""
