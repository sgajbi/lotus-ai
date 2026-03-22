from pathlib import Path

from app.config import settings
from app.repositories.memory_provider_operations_repository import (
    InMemoryProviderOperationsRepository,
)
from app.repositories.sqlalchemy_provider_operations_repository import (
    SqlAlchemyProviderOperationsRepository,
)
from app.services.provider_operations_store import get_provider_operations_store


def test_provider_operations_store_uses_memory_mode_by_default() -> None:
    settings.provider_operations_store_mode = "memory"

    repository = get_provider_operations_store()

    assert isinstance(repository, InMemoryProviderOperationsRepository)


def test_provider_operations_store_uses_sqlalchemy_when_configured(tmp_path: Path) -> None:
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'provider-ops-store.db'}"

    repository = get_provider_operations_store()

    assert isinstance(repository, SqlAlchemyProviderOperationsRepository)
