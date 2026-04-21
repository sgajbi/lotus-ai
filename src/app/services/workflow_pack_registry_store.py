from __future__ import annotations

from app.config import settings
from app.repositories.memory_workflow_pack_registry_repository import (
    InMemoryWorkflowPackRegistryRepository,
)
from app.repositories.workflow_pack_registry_repository import WorkflowPackRegistryRepository
from app.services.workflow_pack_registry_seed import build_seed_workflow_pack_registrations

_memory_repository = InMemoryWorkflowPackRegistryRepository(
    registrations=build_seed_workflow_pack_registrations()
)


def get_workflow_pack_registry_store() -> WorkflowPackRegistryRepository:
    from app.repositories.sqlalchemy_workflow_pack_registry_repository import (
        SqlAlchemyWorkflowPackRegistryRepository,
    )

    global _sqlalchemy_repository

    if settings.workflow_pack_registry_store_mode == "memory":
        return _memory_repository
    if settings.workflow_pack_registry_store_mode == "sqlalchemy":
        if not settings.database_url:
            raise RuntimeError(
                "LOTUS_AI_DATABASE_URL is required when "
                "LOTUS_AI_WORKFLOW_PACK_REGISTRY_STORE_MODE=sqlalchemy."
            )
        if _sqlalchemy_repository is None:
            _sqlalchemy_repository = SqlAlchemyWorkflowPackRegistryRepository(
                settings.database_url,
                default_registrations=build_seed_workflow_pack_registrations(),
            )
        return _sqlalchemy_repository
    raise RuntimeError(
        "Unsupported workflow-pack registry store mode: "
        f"{settings.workflow_pack_registry_store_mode}"
    )


def reset_workflow_pack_registry_store_cache() -> None:
    global _memory_repository
    global _sqlalchemy_repository
    _memory_repository = InMemoryWorkflowPackRegistryRepository(
        registrations=build_seed_workflow_pack_registrations()
    )
    _sqlalchemy_repository = None


_sqlalchemy_repository: WorkflowPackRegistryRepository | None = None
