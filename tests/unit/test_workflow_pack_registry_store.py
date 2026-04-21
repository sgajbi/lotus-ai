from pathlib import Path

from app.repositories.memory_workflow_pack_registry_repository import (
    InMemoryWorkflowPackRegistryRepository,
)
from app.repositories.sqlalchemy_workflow_pack_registry_repository import (
    SqlAlchemyWorkflowPackRegistryRepository,
)
from app.services.workflow_pack_registry_store import (
    get_workflow_pack_registry_store,
    reset_workflow_pack_registry_store_cache,
)
from app.config import settings
from tests.support.migration_runner import upgrade_database_to_head


def test_workflow_pack_registry_store_returns_cached_memory_repository_and_resets() -> None:
    settings.workflow_pack_registry_store_mode = "memory"
    reset_workflow_pack_registry_store_cache()

    first_repository = get_workflow_pack_registry_store()

    assert isinstance(first_repository, InMemoryWorkflowPackRegistryRepository)
    assert first_repository is get_workflow_pack_registry_store()

    reset_workflow_pack_registry_store_cache()

    assert get_workflow_pack_registry_store() is not first_repository


def test_workflow_pack_registry_store_returns_sqlalchemy_repository(tmp_path: Path) -> None:
    settings.workflow_pack_registry_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'workflow-pack-registry-store.db'}"
    upgrade_database_to_head(settings.database_url)
    reset_workflow_pack_registry_store_cache()

    repository = get_workflow_pack_registry_store()

    assert isinstance(repository, SqlAlchemyWorkflowPackRegistryRepository)
    registrations = repository.list_registrations()
    assert [f"{registration.pack_id}@{registration.version}" for registration in registrations] == [
        "advisor_brief.pack@v1",
        "advisor_brief.pack@v2",
        "twr_inspection_support_brief.pack@v1",
        "workspace_rationale.pack@v1",
    ]


def test_workflow_pack_registry_store_rejects_invalid_configuration() -> None:
    settings.workflow_pack_registry_store_mode = "sqlalchemy"
    settings.database_url = None
    reset_workflow_pack_registry_store_cache()

    try:
        get_workflow_pack_registry_store()
    except RuntimeError as exc:
        assert "WORKFLOW_PACK_REGISTRY_STORE_MODE=sqlalchemy" in str(exc)
    else:
        raise AssertionError("Expected missing database configuration to fail")

    settings.workflow_pack_registry_store_mode = "unsupported"

    try:
        get_workflow_pack_registry_store()
    except RuntimeError as exc:
        assert "Unsupported workflow-pack registry store mode" in str(exc)
    else:
        raise AssertionError("Expected unsupported workflow-pack registry store mode to fail")
