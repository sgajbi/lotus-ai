from __future__ import annotations

from app.config import settings
from app.repositories.audit_repository import AuditRepository
from app.repositories.memory_audit_repository import InMemoryAuditRepository
from app.repositories.sqlalchemy_audit_repository import SqlAlchemyAuditRepository

_memory_repository = InMemoryAuditRepository()
_sqlalchemy_repository: SqlAlchemyAuditRepository | None = None


def get_audit_store() -> AuditRepository:
    if settings.audit_store_mode == "memory":
        return _memory_repository
    if settings.audit_store_mode == "sqlalchemy":
        if not settings.database_url:
            raise RuntimeError(
                "LOTUS_AI_DATABASE_URL is required when LOTUS_AI_AUDIT_STORE_MODE=sqlalchemy."
            )
        global _sqlalchemy_repository
        if _sqlalchemy_repository is None:
            _sqlalchemy_repository = SqlAlchemyAuditRepository(settings.database_url)
        return _sqlalchemy_repository
    raise RuntimeError("Unsupported LOTUS_AI_AUDIT_STORE_MODE.")


def reset_audit_store_cache() -> None:
    global _sqlalchemy_repository
    _sqlalchemy_repository = None
