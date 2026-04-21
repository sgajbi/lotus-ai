from pathlib import Path

import pytest

from app.config import settings
from app.repositories.memory_workflow_pack_task_flow_repository import (
    InMemoryWorkflowPackTaskFlowRepository,
)
from app.repositories.sqlalchemy_workflow_pack_task_flow_repository import (
    SqlAlchemyWorkflowPackTaskFlowRepository,
)
from app.services.workflow_pack_task_flow_store import (
    get_workflow_pack_task_flow_store,
    reset_workflow_pack_task_flow_store_cache,
)
from tests.support.migration_runner import upgrade_database_to_head


def test_workflow_pack_task_flow_store_returns_cached_memory_repository_and_resets() -> None:
    settings.workflow_pack_task_flow_store_mode = "memory"
    reset_workflow_pack_task_flow_store_cache()

    first_repository = get_workflow_pack_task_flow_store()

    assert first_repository is get_workflow_pack_task_flow_store()
    assert isinstance(first_repository, InMemoryWorkflowPackTaskFlowRepository)

    reset_workflow_pack_task_flow_store_cache()

    assert get_workflow_pack_task_flow_store() is not first_repository


def test_workflow_pack_task_flow_store_returns_sqlalchemy_repository(tmp_path: Path) -> None:
    settings.workflow_pack_task_flow_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'workflow-pack-task-flow-store.db'}"
    upgrade_database_to_head(settings.database_url)
    reset_workflow_pack_task_flow_store_cache()

    repository = get_workflow_pack_task_flow_store()

    assert isinstance(repository, SqlAlchemyWorkflowPackTaskFlowRepository)


def test_sqlalchemy_task_flow_repository_accepts_in_memory_sqlite() -> None:
    repository = SqlAlchemyWorkflowPackTaskFlowRepository("sqlite:///:memory:")

    assert isinstance(repository, SqlAlchemyWorkflowPackTaskFlowRepository)


def test_sqlalchemy_task_flow_repository_ignores_non_file_sqlite_parent() -> None:
    repository = SqlAlchemyWorkflowPackTaskFlowRepository("sqlite+pysqlite:///:memory:")

    assert isinstance(repository, SqlAlchemyWorkflowPackTaskFlowRepository)


def test_sqlalchemy_task_flow_repository_creates_relative_sqlite_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    SqlAlchemyWorkflowPackTaskFlowRepository("sqlite:///nested/task-flow-store.db")

    assert (tmp_path / "nested").is_dir()


def test_workflow_pack_task_flow_store_rejects_invalid_configuration() -> None:
    settings.workflow_pack_task_flow_store_mode = "sqlalchemy"
    settings.database_url = None
    reset_workflow_pack_task_flow_store_cache()

    with pytest.raises(RuntimeError, match="LOTUS_AI_DATABASE_URL"):
        get_workflow_pack_task_flow_store()

    settings.workflow_pack_task_flow_store_mode = "unsupported"
    with pytest.raises(RuntimeError, match="Unsupported workflow-pack task-flow store mode"):
        get_workflow_pack_task_flow_store()
