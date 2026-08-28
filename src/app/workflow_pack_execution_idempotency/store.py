from __future__ import annotations

from app.config import settings
from app.workflow_pack_execution_idempotency.memory_repository import (
    InMemoryWorkflowPackExecutionIdempotencyRepository,
)
from app.workflow_pack_execution_idempotency.repository import (
    WorkflowPackExecutionIdempotencyRepository,
)
from app.workflow_pack_execution_idempotency.sqlalchemy_repository import (
    SqlAlchemyWorkflowPackExecutionIdempotencyRepository,
)

_memory_repository = InMemoryWorkflowPackExecutionIdempotencyRepository()
_sqlalchemy_repository: SqlAlchemyWorkflowPackExecutionIdempotencyRepository | None = None


def get_workflow_pack_execution_idempotency_store() -> WorkflowPackExecutionIdempotencyRepository:
    if settings.workflow_pack_run_store_mode == "memory":
        return _memory_repository
    if settings.workflow_pack_run_store_mode == "sqlalchemy":
        if not settings.database_url:
            raise RuntimeError(
                "LOTUS_AI_DATABASE_URL is required when the workflow-pack run store mode is "
                "sqlalchemy."
            )
        global _sqlalchemy_repository
        if _sqlalchemy_repository is None:
            _sqlalchemy_repository = SqlAlchemyWorkflowPackExecutionIdempotencyRepository(
                settings.database_url
            )
        return _sqlalchemy_repository
    raise RuntimeError(
        "Unsupported workflow-pack execution idempotency store mode: "
        f"{settings.workflow_pack_run_store_mode}"
    )


def reset_workflow_pack_execution_idempotency_store_cache() -> None:
    global _memory_repository
    global _sqlalchemy_repository
    _memory_repository = InMemoryWorkflowPackExecutionIdempotencyRepository()
    _sqlalchemy_repository = None
