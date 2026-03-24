from __future__ import annotations

from app.config import settings
from app.repositories.caller_policy_repository import CallerPolicyRepository
from app.repositories.memory_caller_policy_repository import InMemoryCallerPolicyRepository
from app.repositories.sqlalchemy_caller_policy_repository import SqlAlchemyCallerPolicyRepository

_memory_repository = InMemoryCallerPolicyRepository()
_sqlalchemy_repository: SqlAlchemyCallerPolicyRepository | None = None


def get_caller_policy_repository() -> CallerPolicyRepository:
    if settings.access_control_store_mode == "memory":
        return _memory_repository
    if settings.access_control_store_mode == "sqlalchemy":
        if not settings.database_url:
            raise RuntimeError(
                "LOTUS_AI_DATABASE_URL is required when LOTUS_AI_ACCESS_CONTROL_STORE_MODE=sqlalchemy."
            )
        global _sqlalchemy_repository
        if _sqlalchemy_repository is None:
            _sqlalchemy_repository = SqlAlchemyCallerPolicyRepository(settings.database_url)
        return _sqlalchemy_repository
    raise RuntimeError("Unsupported LOTUS_AI_ACCESS_CONTROL_STORE_MODE.")


def reset_caller_policy_store_cache() -> None:
    global _memory_repository
    global _sqlalchemy_repository
    _memory_repository = InMemoryCallerPolicyRepository()
    _sqlalchemy_repository = None
