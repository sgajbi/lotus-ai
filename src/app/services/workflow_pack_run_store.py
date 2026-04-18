from __future__ import annotations

from app.config import settings
from app.repositories.memory_workflow_pack_run_repository import InMemoryWorkflowPackRunRepository
from app.repositories.workflow_pack_run_repository import WorkflowPackRunRepository

_memory_repository = InMemoryWorkflowPackRunRepository()


def get_workflow_pack_run_store() -> WorkflowPackRunRepository:
    if settings.workflow_pack_run_store_mode == "memory":
        return _memory_repository
    raise RuntimeError(
        "Unsupported LOTUS_AI_WORKFLOW_PACK_RUN_STORE_MODE. Only 'memory' is currently implemented."
    )


def reset_workflow_pack_run_store_cache() -> None:
    global _memory_repository
    _memory_repository = InMemoryWorkflowPackRunRepository()
