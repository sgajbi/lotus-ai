from __future__ import annotations

from collections.abc import Sequence

from dataclasses import dataclass
from typing import Protocol

from app.provider_retention_confirmations.contracts import (
    ProviderRetentionConfirmationEnvelope,
)


class ProviderRetentionConfirmationConflictError(ValueError):
    pass


@dataclass(frozen=True)
class ProviderRetentionConfirmationRecord:
    idempotency_key: str
    request_fingerprint: str
    envelope: ProviderRetentionConfirmationEnvelope


class ProviderRetentionConfirmationRepository(Protocol):
    def get_by_idempotency_key(
        self, *, idempotency_key: str
    ) -> ProviderRetentionConfirmationRecord | None: ...

    def get_by_provider_confirmation_ref(
        self, *, provider_confirmation_ref: str
    ) -> ProviderRetentionConfirmationRecord | None: ...

    def list_confirmations(self, *, limit: int) -> list[ProviderRetentionConfirmationRecord]:
        """List confirmations, newest first (lifecycle engine read)."""
        ...

    def delete_confirmations(self, confirmation_ids: Sequence[str]) -> int:
        """Delete confirmation evidence by id (issue #158, S2b)."""
        ...

    def save(
        self, record: ProviderRetentionConfirmationRecord
    ) -> ProviderRetentionConfirmationRecord: ...
