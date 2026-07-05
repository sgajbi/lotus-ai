from pathlib import Path

import pytest

from app.config import settings
from app.repositories.workflow_pack_run_repository import WorkflowPackRunRecord
from app.repositories.memory_workflow_pack_run_repository import InMemoryWorkflowPackRunRepository
from app.repositories.sqlalchemy_workflow_pack_run_repository import (
    SqlAlchemyWorkflowPackRunRepository,
)
from app.services.workflow_pack_run_store import (
    get_workflow_pack_run_store,
    reset_workflow_pack_run_store_cache,
)
from tests.support.migration_runner import upgrade_database_to_head


def _workflow_pack_run_record(
    *,
    run_id: str,
    pack_id: str = "advisor_brief.pack",
    caller_app: str = "lotus-gateway",
    tenant_id: str | None = "tenant-sg-001",
    workflow_surface: str | None = "advisor-brief-workspace",
    runtime_state: str = "COMPLETED",
    review_state: str = "AWAITING_REVIEW",
    workflow_authority_owner: str = "lotus-gateway",
    created_at: str = "2026-04-19T10:00:00Z",
) -> WorkflowPackRunRecord:
    return WorkflowPackRunRecord(
        run_id=run_id,
        pack_id=pack_id,
        pack_family=pack_id.removesuffix(".pack"),
        pack_version="v1",
        registration_ref=f"{pack_id}@v1",
        task_id="explain.v1",
        request_id=f"req-{run_id}",
        caller_app=caller_app,
        correlation_id=f"corr-{run_id}",
        tenant_id=tenant_id,
        workflow_surface=workflow_surface,
        workflow_authority_owner=workflow_authority_owner,
        runtime_state=runtime_state,
        review_state=review_state,
        review_required=True,
        provider_mode="catalog_only",
        stubbed=True,
        output_preview="preview",
        structured_output_keys=[],
        evidence_descriptors=[],
        artifact_refs=[],
        supersedes_run_id=None,
        superseded_by_run_id=None,
        created_at=created_at,
        completed_at=created_at,
        last_updated_at=created_at,
    )


def test_workflow_pack_run_store_returns_cached_memory_repository_and_resets() -> None:
    settings.workflow_pack_run_store_mode = "memory"
    reset_workflow_pack_run_store_cache()

    first_repository = get_workflow_pack_run_store()

    assert first_repository is get_workflow_pack_run_store()
    assert isinstance(first_repository, InMemoryWorkflowPackRunRepository)

    reset_workflow_pack_run_store_cache()

    assert get_workflow_pack_run_store() is not first_repository


def test_workflow_pack_run_store_returns_sqlalchemy_repository(tmp_path: Path) -> None:
    settings.workflow_pack_run_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'workflow-pack-run-store.db'}"
    upgrade_database_to_head(settings.database_url)
    reset_workflow_pack_run_store_cache()

    repository = get_workflow_pack_run_store()

    assert isinstance(repository, SqlAlchemyWorkflowPackRunRepository)


def _assert_workflow_pack_run_repository_queries_filtered_newest_records(
    repository: InMemoryWorkflowPackRunRepository | SqlAlchemyWorkflowPackRunRepository,
) -> None:
    repository.save_run(
        _workflow_pack_run_record(run_id="run-old", created_at="2026-04-19T09:00:00Z")
    )
    repository.save_run(
        _workflow_pack_run_record(run_id="run-new", created_at="2026-04-19T11:00:00Z")
    )
    repository.save_run(
        _workflow_pack_run_record(
            run_id="run-other",
            caller_app="lotus-advise",
            created_at="2026-04-19T12:00:00Z",
        )
    )

    results = repository.query_runs(
        registration_ref="advisor_brief.pack@v1",
        pack_id="advisor_brief.pack",
        caller_app="lotus-gateway",
        tenant_id="tenant-sg-001",
        workflow_surface="advisor-brief-workspace",
        runtime_state="COMPLETED",
        review_state="AWAITING_REVIEW",
        workflow_authority_owner="lotus-gateway",
        limit=1,
    )

    assert [record.run_id for record in results] == ["run-new"]


def test_memory_workflow_pack_run_repository_queries_filtered_newest_records() -> None:
    _assert_workflow_pack_run_repository_queries_filtered_newest_records(
        InMemoryWorkflowPackRunRepository()
    )


def test_sqlalchemy_workflow_pack_run_repository_queries_filtered_newest_records(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'workflow-pack-run-query.db'}"
    upgrade_database_to_head(database_url)
    _assert_workflow_pack_run_repository_queries_filtered_newest_records(
        SqlAlchemyWorkflowPackRunRepository(database_url)
    )


def test_workflow_pack_run_store_rejects_invalid_configuration() -> None:
    settings.workflow_pack_run_store_mode = "sqlalchemy"
    settings.database_url = None
    reset_workflow_pack_run_store_cache()

    with pytest.raises(RuntimeError, match="LOTUS_AI_DATABASE_URL"):
        get_workflow_pack_run_store()

    settings.workflow_pack_run_store_mode = "unsupported"
    with pytest.raises(RuntimeError, match="Unsupported workflow-pack run store mode"):
        get_workflow_pack_run_store()
