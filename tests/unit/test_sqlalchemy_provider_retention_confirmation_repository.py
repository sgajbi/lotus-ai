from pathlib import Path

from app.provider_retention_confirmations.memory_repository import (
    InMemoryProviderRetentionConfirmationRepository,
)
from app.provider_retention_confirmations.repository import (
    ProviderRetentionConfirmationRecord,
)
from app.provider_retention_confirmations.sqlalchemy_repository import (
    SqlAlchemyProviderRetentionConfirmationRepository,
)
from tests.support.migration_runner import upgrade_database_to_head
from tests.unit.test_provider_retention_confirmation import BASE_RUN, _issue, _request


def test_sqlalchemy_confirmation_survives_repository_restart(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'provider-retention.sqlite3'}"
    upgrade_database_to_head(database_url)
    envelope = _issue(BASE_RUN, _request())
    record = ProviderRetentionConfirmationRecord(
        idempotency_key="sql-provider-retention-001",
        request_fingerprint="f" * 64,
        envelope=envelope,
    )
    first = SqlAlchemyProviderRetentionConfirmationRepository(database_url)
    first.save(record)
    first.close()

    restarted = SqlAlchemyProviderRetentionConfirmationRepository(database_url)
    loaded = restarted.get_by_idempotency_key(idempotency_key="sql-provider-retention-001")
    loaded_by_provider_ref = restarted.get_by_provider_confirmation_ref(
        provider_confirmation_ref="provider-confirmation-001"
    )
    restarted.close()

    assert loaded == record
    assert loaded_by_provider_ref == record


def test_memory_repository_replays_same_record() -> None:
    envelope = _issue(BASE_RUN, _request())
    record = ProviderRetentionConfirmationRecord(
        idempotency_key="memory-provider-retention-001",
        request_fingerprint="f" * 64,
        envelope=envelope,
    )
    repository = InMemoryProviderRetentionConfirmationRepository()

    assert repository.save(record) == record
    assert repository.save(record) == record
