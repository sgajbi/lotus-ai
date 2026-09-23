"""PostgreSQL proof for the canonical lotus-advise tenant admission (#379)."""

from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.repositories.sqlalchemy_workflow_pack_task_flow_repository import (
    SqlAlchemyWorkflowPackTaskFlowRepository,
)
from app.repositories.workflow_pack_task_flow_repository import (
    WorkflowPackTaskFlowCheckpointRecord,
    WorkflowPackTaskFlowRecord,
)
from app.services.workflow_pack_task_flow_recording import (
    build_workflow_pack_checkpoint_id,
    build_workflow_pack_task_flow_id,
)
from tests.support.workflow_pack_task_flow_fixtures import (
    workflow_pack_task_flow_checkpoint,
    workflow_pack_task_flow_descriptor,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PRIOR_REVISION = "0076_manifest_content_digest"
_HEAD_REVISION = "head"


def _migrate(database_url: str, revision: str) -> None:
    config = Config(str(_REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_REPO_ROOT / "alembic"))
    prior_lotus_ai_url = os.environ.get("LOTUS_AI_DATABASE_URL")
    prior_database_url = os.environ.get("DATABASE_URL")
    os.environ["LOTUS_AI_DATABASE_URL"] = database_url
    os.environ["DATABASE_URL"] = database_url
    try:
        if revision == _HEAD_REVISION:
            command.upgrade(config, revision)
        else:
            command.downgrade(config, revision)
    finally:
        if prior_lotus_ai_url is None:
            os.environ.pop("LOTUS_AI_DATABASE_URL", None)
        else:
            os.environ["LOTUS_AI_DATABASE_URL"] = prior_lotus_ai_url
        if prior_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = prior_database_url


def _policy(database_url: str) -> tuple[str, list[str], bool]:
    engine = create_engine(database_url, future=True)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT tenant_policy_mode, restricted_tenant_ids, allow_live_provider
                    FROM caller_policies
                    WHERE caller_app = 'lotus-advise'
                    """
                )
            ).one()
    finally:
        engine.dispose()
    return row.tenant_policy_mode, list(row.restricted_tenant_ids), row.allow_live_provider


def test_lotus_advise_canonical_tenant_migration_upgrades_and_rolls_back_on_postgres(
    postgres_database_url: str,
) -> None:
    try:
        assert _policy(postgres_database_url) == (
            "RESTRICTED",
            ["tenant-us-002", "tenant-sg-001", "tenant-sg"],
            False,
        )

        _migrate(postgres_database_url, _PRIOR_REVISION)
        assert _policy(postgres_database_url) == (
            "RESTRICTED",
            ["tenant-us-002", "tenant-sg-001"],
            False,
        )

        _migrate(postgres_database_url, _HEAD_REVISION)
        assert _policy(postgres_database_url) == (
            "RESTRICTED",
            ["tenant-us-002", "tenant-sg-001", "tenant-sg"],
            False,
        )
    finally:
        _migrate(postgres_database_url, _HEAD_REVISION)


def test_longest_supported_copilot_checkpoint_id_persists_on_postgres(
    postgres_database_url: str,
) -> None:
    request_id = "air_805a9f53c5664caf9514b1fbd2c17b60"
    task_flow_id = build_workflow_pack_task_flow_id(
        pack_family="advisory_copilot_proposal_explanation",
        request_id=request_id,
    )
    checkpoint_id = build_workflow_pack_checkpoint_id(
        task_flow_id=task_flow_id,
        request_id=request_id,
    )
    repository = SqlAlchemyWorkflowPackTaskFlowRepository(postgres_database_url)
    task_flow = workflow_pack_task_flow_descriptor(task_flow_id=task_flow_id)
    checkpoint = workflow_pack_task_flow_checkpoint(
        checkpoint_id=checkpoint_id,
        task_flow_id=task_flow_id,
    )

    repository.save_task_flow(WorkflowPackTaskFlowRecord(descriptor=task_flow))
    repository.save_checkpoint(WorkflowPackTaskFlowCheckpointRecord(descriptor=checkpoint))

    persisted = repository.list_checkpoints(task_flow_id=task_flow_id)
    assert len(checkpoint_id) <= 128
    assert [record.descriptor.checkpoint_id for record in persisted] == [checkpoint_id]
