from __future__ import annotations

from app.config import settings
from app.repositories.memory_workflow_pack_task_flow_repository import (
    InMemoryWorkflowPackTaskFlowRepository,
)
from app.repositories.sqlalchemy_workflow_pack_task_flow_repository import (
    SqlAlchemyWorkflowPackTaskFlowRepository,
)
from app.repositories.workflow_pack_task_flow_repository import WorkflowPackTaskFlowRepository

_memory_repository = InMemoryWorkflowPackTaskFlowRepository()
_sqlalchemy_repository: SqlAlchemyWorkflowPackTaskFlowRepository | None = None


def get_workflow_pack_task_flow_store() -> WorkflowPackTaskFlowRepository:
    if settings.workflow_pack_task_flow_store_mode == "memory":
        return _memory_repository
    if settings.workflow_pack_task_flow_store_mode == "sqlalchemy":
        if not settings.database_url:
            raise RuntimeError(
                "LOTUS_AI_DATABASE_URL is required when "
                "LOTUS_AI_WORKFLOW_PACK_TASK_FLOW_STORE_MODE=sqlalchemy."
            )
        global _sqlalchemy_repository
        if _sqlalchemy_repository is None:
            _sqlalchemy_repository = SqlAlchemyWorkflowPackTaskFlowRepository(settings.database_url)
        return _sqlalchemy_repository
    raise RuntimeError(
        "Unsupported workflow-pack task-flow store mode: "
        f"{settings.workflow_pack_task_flow_store_mode}"
    )


def reset_workflow_pack_task_flow_store_cache() -> None:
    global _memory_repository
    global _sqlalchemy_repository
    _memory_repository = InMemoryWorkflowPackTaskFlowRepository()
    _sqlalchemy_repository = None
