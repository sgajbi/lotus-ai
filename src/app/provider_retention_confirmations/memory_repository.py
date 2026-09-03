from __future__ import annotations

from collections.abc import Sequence

from app.provider_retention_confirmations.repository import (
    ProviderRetentionConfirmationConflictError,
    ProviderRetentionConfirmationRecord,
)


class InMemoryProviderRetentionConfirmationRepository:
    def __init__(self) -> None:
        self._records: dict[str, ProviderRetentionConfirmationRecord] = {}
        self._idempotency_key_by_provider_ref: dict[str, str] = {}

    def get_by_idempotency_key(
        self, *, idempotency_key: str
    ) -> ProviderRetentionConfirmationRecord | None:
        return self._records.get(idempotency_key)

    def get_by_provider_confirmation_ref(
        self, *, provider_confirmation_ref: str
    ) -> ProviderRetentionConfirmationRecord | None:
        idempotency_key = self._idempotency_key_by_provider_ref.get(provider_confirmation_ref)
        return self._records.get(idempotency_key) if idempotency_key is not None else None

    def list_confirmations(self, *, limit: int) -> list[ProviderRetentionConfirmationRecord]:
        records = sorted(
            self._records.values(),
            key=lambda record: record.envelope.claims.issued_at_utc,
            reverse=True,
        )
        return records[:limit]

    def delete_confirmations(self, confirmation_ids: Sequence[str]) -> int:
        wanted = set(confirmation_ids)
        deleted = 0
        for idempotency_key, record in list(self._records.items()):
            if record.envelope.claims.confirmation_id in wanted:
                self._records.pop(idempotency_key, None)
                self._idempotency_key_by_provider_ref.pop(
                    record.envelope.claims.provider_confirmation_ref, None
                )
                deleted += 1
        return deleted

    def save(
        self, record: ProviderRetentionConfirmationRecord
    ) -> ProviderRetentionConfirmationRecord:
        existing = self._records.get(record.idempotency_key)
        if existing is not None:
            if existing.request_fingerprint != record.request_fingerprint:
                raise ProviderRetentionConfirmationConflictError(
                    "idempotency key was reused with different provider confirmation input"
                )
            return existing
        self._records[record.idempotency_key] = record
        self._idempotency_key_by_provider_ref[record.envelope.claims.provider_confirmation_ref] = (
            record.idempotency_key
        )
        return record
