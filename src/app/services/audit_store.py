from __future__ import annotations

from app.config import settings
from app.repositories.audit_repository import AuditRepository
from app.repositories.memory_audit_repository import InMemoryAuditRepository

_memory_repository = InMemoryAuditRepository()


def get_audit_store() -> AuditRepository:
    if settings.audit_store_mode == "memory":
        return _memory_repository
    raise RuntimeError(
        "Unsupported LOTUS_AI_AUDIT_STORE_MODE. "
        "Only 'memory' is currently wired in this phase."
    )
