from pathlib import Path

import pytest

from app.config import settings
from app.contracts.workflow_pack_task_flows import WorkflowPackTaskFlowStatus
from app.repositories.memory_workflow_pack_task_flow_repository import (
    InMemoryWorkflowPackTaskFlowRepository,
)
from app.repositories.sqlalchemy_workflow_pack_task_flow_repository import (
    SqlAlchemyWorkflowPackTaskFlowRepository,
)
from app.repositories.workflow_pack_task_flow_repository import WorkflowPackTaskFlowRecord
from app.services.workflow_pack_task_flow_store import (
    get_workflow_pack_task_flow_store,
    reset_workflow_pack_task_flow_store_cache,
)
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.workflow_pack_task_flow_fixtures import workflow_pack_task_flow_descriptor


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


def test_sqlalchemy_task_flow_repository_returns_none_for_missing_record(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'workflow-pack-task-flow-store.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyWorkflowPackTaskFlowRepository(database_url)

    assert repository.get_task_flow(task_flow_id="missing-task-flow") is None


def _assert_task_flow_repository_queries_catalog_and_run_refs(
    repository: InMemoryWorkflowPackTaskFlowRepository | SqlAlchemyWorkflowPackTaskFlowRepository,
) -> None:
    older = workflow_pack_task_flow_descriptor(
        task_flow_id="task-flow-old",
        flow_status=WorkflowPackTaskFlowStatus.WAITING_FOR_REVIEW,
        current_step_id="draft-brief",
        updated_at="2026-04-21T01:00:00Z",
    )
    newer = workflow_pack_task_flow_descriptor(
        task_flow_id="task-flow-new",
        flow_status=WorkflowPackTaskFlowStatus.WAITING_FOR_REVIEW,
        current_step_id="draft-brief",
        updated_at="2026-04-21T01:02:00Z",
    ).model_copy(update={"run_refs": ["run-002"]})
    other = workflow_pack_task_flow_descriptor(
        task_flow_id="task-flow-other",
        updated_at="2026-04-21T01:03:00Z",
    ).model_copy(update={"caller": "lotus-advise", "run_refs": ["run-003"]})
    for descriptor in (older, newer, other):
        repository.save_task_flow(WorkflowPackTaskFlowRecord(descriptor=descriptor))

    filtered = repository.query_task_flows(
        workflow_pack_id="advisor_brief.pack",
        caller="lotus-gateway",
        tenant_id="tenant-sg-001",
        workflow_surface="advisor-brief-panel",
        flow_status="WAITING_FOR_REVIEW",
        supportability_status="ACTION_REQUIRED",
        limit=1,
    )
    by_run_ref = repository.list_task_flows_by_run_ref(run_id="run-002", limit=10)

    assert [record.descriptor.task_flow_id for record in filtered] == ["task-flow-new"]
    assert [record.descriptor.task_flow_id for record in by_run_ref] == ["task-flow-new"]


def test_memory_task_flow_repository_queries_catalog_and_run_refs() -> None:
    _assert_task_flow_repository_queries_catalog_and_run_refs(
        InMemoryWorkflowPackTaskFlowRepository()
    )


def test_sqlalchemy_task_flow_repository_queries_catalog_and_run_refs(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'workflow-pack-task-flow-query.db'}"
    upgrade_database_to_head(database_url)
    _assert_task_flow_repository_queries_catalog_and_run_refs(
        SqlAlchemyWorkflowPackTaskFlowRepository(database_url)
    )


def test_workflow_pack_task_flow_store_rejects_invalid_configuration() -> None:
    settings.workflow_pack_task_flow_store_mode = "sqlalchemy"
    settings.database_url = None
    reset_workflow_pack_task_flow_store_cache()

    with pytest.raises(RuntimeError, match="LOTUS_AI_DATABASE_URL"):
        get_workflow_pack_task_flow_store()

    settings.workflow_pack_task_flow_store_mode = "unsupported"
    with pytest.raises(RuntimeError, match="Unsupported workflow-pack task-flow store mode"):
        get_workflow_pack_task_flow_store()
