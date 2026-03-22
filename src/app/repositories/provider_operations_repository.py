from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.contracts.providers import ProviderFailureCategory, ProviderQuotaScope


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
class ProviderDegradationStateRecord:
    degradation_key: str
    consecutive_failure_count: int
    last_failure_category: ProviderFailureCategory | None
    circuit_open_until: str | None
    timeout_failure_count: int
    rate_limited_failure_count: int
    upstream_error_failure_count: int
    updated_at: str


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
