from app.config import settings
from app.contracts.runtime_readiness import RuntimeReadinessStatus
from app.services.runtime_readiness import (
    get_audit_store_runtime_status,
    get_retrieval_store_runtime_status,
)


def test_audit_store_runtime_status_defaults_to_ready_memory_mode() -> None:
    settings.audit_store_mode = "memory"
    settings.database_url = None

    status_descriptor = get_audit_store_runtime_status()

    assert status_descriptor.mode == "memory"
    assert status_descriptor.status == RuntimeReadinessStatus.READY


def test_retrieval_store_runtime_status_requires_database_for_sqlalchemy_mode() -> None:
    settings.retrieval_store_mode = "sqlalchemy"
    settings.database_url = None

    status_descriptor = get_retrieval_store_runtime_status()

    assert status_descriptor.mode == "sqlalchemy"
    assert status_descriptor.status == RuntimeReadinessStatus.CONFIGURATION_REQUIRED

    settings.retrieval_store_mode = "memory"
