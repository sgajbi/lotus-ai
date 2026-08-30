from __future__ import annotations

from app.config import settings
from app.repositories.kill_switch_repository import KillSwitchRepository
from app.repositories.memory_kill_switch_repository import InMemoryKillSwitchRepository
from app.repositories.sqlalchemy_kill_switch_repository import SqlAlchemyKillSwitchRepository

_memory_repository = InMemoryKillSwitchRepository()
_sqlalchemy_repository: SqlAlchemyKillSwitchRepository | None = None


def get_kill_switch_repository() -> KillSwitchRepository:
    if settings.kill_switch_store_mode == "memory":
        return _memory_repository
    if settings.kill_switch_store_mode == "sqlalchemy":
        if not settings.database_url:
            raise RuntimeError(
                "LOTUS_AI_DATABASE_URL is required when LOTUS_AI_KILL_SWITCH_STORE_MODE=sqlalchemy."
            )
        global _sqlalchemy_repository
        if _sqlalchemy_repository is None:
            _sqlalchemy_repository = SqlAlchemyKillSwitchRepository(settings.database_url)
        return _sqlalchemy_repository
    raise RuntimeError("Unsupported LOTUS_AI_KILL_SWITCH_STORE_MODE.")


def reset_kill_switch_store_cache() -> None:
    global _memory_repository
    global _sqlalchemy_repository
    _memory_repository = InMemoryKillSwitchRepository()
    _sqlalchemy_repository = None
