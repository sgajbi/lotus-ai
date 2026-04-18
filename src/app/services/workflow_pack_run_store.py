from __future__ import annotations

from app.config import settings
from app.repositories.memory_workflow_pack_run_repository import InMemoryWorkflowPackRunRepository
from app.repositories.sqlalchemy_workflow_pack_run_repository import (
    SqlAlchemyWorkflowPackRunRepository,
)
from app.repositories.workflow_pack_run_repository import WorkflowPackRunRepository

_memory_repository = InMemoryWorkflowPackRunRepository()
_sqlalchemy_repository: SqlAlchemyWorkflowPackRunRepository | None = None


def get_workflow_pack_run_store() -> WorkflowPackRunRepository:
    if settings.workflow_pack_run_store_mode == "memory":
        return _memory_repository
    if settings.workflow_pack_run_store_mode == "sqlalchemy":
        if not settings.database_url:
            raise RuntimeError(
                "LOTUS_AI_DATABASE_URL is required when "
                "LOTUS_AI_WORKFLOW_PACK_RUN_STORE_MODE=sqlalchemy."
            )
        global _sqlalchemy_repository
        if _sqlalchemy_repository is None:
            _sqlalchemy_repository = SqlAlchemyWorkflowPackRunRepository(settings.database_url)
        return _sqlalchemy_repository
    raise RuntimeError(
        f"Unsupported workflow-pack run store mode: {settings.workflow_pack_run_store_mode}"
    )


def reset_workflow_pack_run_store_cache() -> None:
    global _memory_repository
    global _sqlalchemy_repository
    _memory_repository = InMemoryWorkflowPackRunRepository()
    _sqlalchemy_repository = None
