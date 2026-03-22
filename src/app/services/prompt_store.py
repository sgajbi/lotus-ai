from __future__ import annotations

from app.config import settings
from app.repositories.memory_prompt_repository import InMemoryPromptRepository
from app.repositories.prompt_repository import PromptRepository
from app.repositories.sqlalchemy_prompt_repository import SqlAlchemyPromptRepository

_memory_prompt_repository = InMemoryPromptRepository()
_sqlalchemy_prompt_repository: SqlAlchemyPromptRepository | None = None


def get_prompt_repository() -> PromptRepository:
    if settings.prompt_store_mode == "memory":
        return _memory_prompt_repository
    if settings.prompt_store_mode == "sqlalchemy":
        if not settings.database_url:
            raise RuntimeError(
                "LOTUS_AI_DATABASE_URL is required when LOTUS_AI_PROMPT_STORE_MODE=sqlalchemy."
            )
        global _sqlalchemy_prompt_repository
        if _sqlalchemy_prompt_repository is None:
            _sqlalchemy_prompt_repository = SqlAlchemyPromptRepository(settings.database_url)
        return _sqlalchemy_prompt_repository
    raise RuntimeError("Unsupported LOTUS_AI_PROMPT_STORE_MODE.")


def reset_prompt_store_cache() -> None:
    global _sqlalchemy_prompt_repository
    _sqlalchemy_prompt_repository = None
