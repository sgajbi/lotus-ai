from __future__ import annotations

import pytest
from pytest import MonkeyPatch

from app.config import settings
from app.provider_retention_confirmations.memory_repository import (
    InMemoryProviderRetentionConfirmationRepository,
)
from app.provider_retention_confirmations.sqlalchemy_repository import (
    SqlAlchemyProviderRetentionConfirmationRepository,
)
from app.provider_retention_confirmations.store import (
    get_provider_retention_confirmation_store,
    reset_provider_retention_confirmation_store_cache,
)


def test_store_factory_selects_memory_and_caches_sqlalchemy(
    monkeypatch: MonkeyPatch,
    tmp_path: object,
) -> None:
    reset_provider_retention_confirmation_store_cache()
    monkeypatch.setattr(settings, "provider_retention_confirmation_store_mode", "memory")
    assert isinstance(
        get_provider_retention_confirmation_store(),
        InMemoryProviderRetentionConfirmationRepository,
    )

    database_path = str(tmp_path) + "/retention-confirmations.db"
    monkeypatch.setattr(settings, "provider_retention_confirmation_store_mode", "sqlalchemy")
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{database_path}")
    first = get_provider_retention_confirmation_store()
    assert isinstance(first, SqlAlchemyProviderRetentionConfirmationRepository)
    assert get_provider_retention_confirmation_store() is first


def test_store_factory_fails_closed_for_invalid_configuration(monkeypatch: MonkeyPatch) -> None:
    reset_provider_retention_confirmation_store_cache()
    monkeypatch.setattr(settings, "provider_retention_confirmation_store_mode", "sqlalchemy")
    monkeypatch.setattr(settings, "database_url", None)
    with pytest.raises(RuntimeError, match="LOTUS_AI_DATABASE_URL"):
        get_provider_retention_confirmation_store()

    monkeypatch.setattr(settings, "provider_retention_confirmation_store_mode", "unsupported")
    with pytest.raises(RuntimeError, match="Unsupported"):
        get_provider_retention_confirmation_store()
