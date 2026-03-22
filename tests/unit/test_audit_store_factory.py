from pathlib import Path

from app.config import settings
from app.repositories.memory_audit_repository import InMemoryAuditRepository
from app.repositories.sqlalchemy_audit_repository import SqlAlchemyAuditRepository
from app.services.audit_store import get_audit_store, reset_audit_store_cache
from tests.support.migration_runner import upgrade_database_to_head


def test_get_audit_store_returns_memory_repository_by_default() -> None:
    settings.audit_store_mode = "memory"
    reset_audit_store_cache()

    repository = get_audit_store()

    assert isinstance(repository, InMemoryAuditRepository)


def test_get_audit_store_returns_sqlalchemy_repository(tmp_path: Path) -> None:
    settings.audit_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'factory-audit.db'}"
    upgrade_database_to_head(settings.database_url)
    reset_audit_store_cache()

    repository = get_audit_store()

    assert isinstance(repository, SqlAlchemyAuditRepository)

    settings.audit_store_mode = "memory"
    settings.database_url = None
    reset_audit_store_cache()
