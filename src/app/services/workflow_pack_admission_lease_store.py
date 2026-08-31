from __future__ import annotations

from app.config import settings
from app.repositories.memory_workflow_pack_admission_lease_repository import (
    InMemoryWorkflowPackAdmissionLeaseRepository,
)
from app.repositories.sqlalchemy_workflow_pack_admission_lease_repository import (
    SqlAlchemyWorkflowPackAdmissionLeaseRepository,
)
from app.repositories.workflow_pack_admission_lease_repository import (
    WorkflowPackAdmissionLeaseRepository,
)

_memory_repository = InMemoryWorkflowPackAdmissionLeaseRepository()
_sqlalchemy_repository: SqlAlchemyWorkflowPackAdmissionLeaseRepository | None = None


def get_workflow_pack_admission_lease_repository() -> WorkflowPackAdmissionLeaseRepository:
    if settings.workflow_pack_admission_store_mode == "memory":
        return _memory_repository
    if settings.workflow_pack_admission_store_mode == "sqlalchemy":
        if not settings.database_url:
            raise RuntimeError(
                "LOTUS_AI_DATABASE_URL is required when "
                "LOTUS_AI_WORKFLOW_PACK_ADMISSION_STORE_MODE=sqlalchemy."
            )
        global _sqlalchemy_repository
        if _sqlalchemy_repository is None:
            _sqlalchemy_repository = SqlAlchemyWorkflowPackAdmissionLeaseRepository(
                settings.database_url
            )
        return _sqlalchemy_repository

    raise RuntimeError("Unsupported LOTUS_AI_WORKFLOW_PACK_ADMISSION_STORE_MODE.")


def reset_workflow_pack_admission_lease_store_cache() -> None:
    global _memory_repository
    global _sqlalchemy_repository
    _memory_repository = InMemoryWorkflowPackAdmissionLeaseRepository()
    _sqlalchemy_repository = None
