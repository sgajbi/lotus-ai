from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models import ProviderRetentionConfirmationModel
from app.provider_retention_confirmations.contracts import (
    ProviderRetentionConfirmationEnvelope,
)
from app.provider_retention_confirmations.repository import (
    ProviderRetentionConfirmationConflictError,
    ProviderRetentionConfirmationRecord,
)
from app.repositories.sqlalchemy_repository_base import SqlAlchemyRepositoryBase


class SqlAlchemyProviderRetentionConfirmationRepository(SqlAlchemyRepositoryBase):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        if database_url.startswith("sqlite"):
            database_path = database_url.split("///", maxsplit=1)[-1]
            if database_path and database_path != ":memory:":
                Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self._configure_sqlalchemy(database_url)

    def get_by_idempotency_key(
        self, *, idempotency_key: str
    ) -> ProviderRetentionConfirmationRecord | None:
        with self._session_factory() as session:
            model = session.scalar(
                select(ProviderRetentionConfirmationModel).where(
                    ProviderRetentionConfirmationModel.idempotency_key == idempotency_key
                )
            )
            return self._to_record(model) if model is not None else None

    def get_by_provider_confirmation_ref(
        self, *, provider_confirmation_ref: str
    ) -> ProviderRetentionConfirmationRecord | None:
        with self._session_factory() as session:
            model = session.scalar(
                select(ProviderRetentionConfirmationModel).where(
                    ProviderRetentionConfirmationModel.provider_confirmation_ref
                    == provider_confirmation_ref
                )
            )
            return self._to_record(model) if model is not None else None

    def save(
        self, record: ProviderRetentionConfirmationRecord
    ) -> ProviderRetentionConfirmationRecord:
        model = ProviderRetentionConfirmationModel(
            confirmation_id=record.envelope.claims.confirmation_id,
            workflow_run_id=record.envelope.claims.workflow_run_id,
            tenant_id=record.envelope.claims.tenant_id,
            provider_confirmation_ref=(record.envelope.claims.provider_confirmation_ref),
            idempotency_key=record.idempotency_key,
            request_fingerprint=record.request_fingerprint,
            outcome=record.envelope.claims.outcome.value,
            envelope_payload=record.envelope.model_dump(mode="json"),
            recorded_at=record.envelope.claims.issued_at_utc,
        )
        with self._session_factory() as session:
            session.add(model)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                existing = self.get_by_idempotency_key(idempotency_key=record.idempotency_key)
                if existing and existing.request_fingerprint == record.request_fingerprint:
                    return existing
                raise ProviderRetentionConfirmationConflictError(
                    "idempotency key was reused with different provider confirmation input"
                ) from exc
        return record

    @staticmethod
    def _to_record(
        model: ProviderRetentionConfirmationModel,
    ) -> ProviderRetentionConfirmationRecord:
        return ProviderRetentionConfirmationRecord(
            idempotency_key=model.idempotency_key,
            request_fingerprint=model.request_fingerprint,
            envelope=ProviderRetentionConfirmationEnvelope.model_validate(model.envelope_payload),
        )
