from pathlib import Path

import pytest

from app.config import settings
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
)
from app.contracts.workflow_pack_task_flows import (
    WorkflowPackTaskFlowStatus,
)
from app.services.workflow_pack_task_flow_service import (
    WorkflowPackTaskFlowNotFoundError,
    create_task_flow,
    get_task_flow,
    list_task_flow_checkpoints,
    record_task_flow_checkpoint,
)
from app.services.workflow_pack_task_flow_store import reset_workflow_pack_task_flow_store_cache
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.workflow_pack_task_flow_fixtures import (
    workflow_pack_task_flow_checkpoint,
    workflow_pack_task_flow_descriptor,
)


def test_task_flow_service_records_checkpoint_and_preserves_state_boundaries() -> None:
    created = create_task_flow(workflow_pack_task_flow_descriptor())

    updated = record_task_flow_checkpoint(
        task_flow_id=created.task_flow_id,
        checkpoint=workflow_pack_task_flow_checkpoint(),
        resulting_status=WorkflowPackTaskFlowStatus.RUNNING,
        current_step_id="draft-brief",
        updated_at="2026-04-21T01:01:00Z",
    )

    assert updated.flow_status == WorkflowPackTaskFlowStatus.RUNNING
    assert updated.runtime_states["run-001"] == WorkflowPackRunRuntimeState.STAGED
    assert updated.review_states["run-001"] == WorkflowPackRunReviewState.AWAITING_REVIEW
    assert updated.checkpoint_refs == ["checkpoint-001"]
    assert updated.step_statuses[0].checkpoint_refs == ["checkpoint-001"]
    assert get_task_flow("task-flow-001") == updated
    assert [
        checkpoint.checkpoint_id for checkpoint in list_task_flow_checkpoints("task-flow-001")
    ] == ["checkpoint-001"]


def test_task_flow_service_rejects_invalid_terminal_transition() -> None:
    completed = workflow_pack_task_flow_descriptor().model_copy(
        update={"flow_status": WorkflowPackTaskFlowStatus.COMPLETED}
    )
    create_task_flow(completed)

    with pytest.raises(ValueError, match="COMPLETED to RUNNING"):
        record_task_flow_checkpoint(
            task_flow_id=completed.task_flow_id,
            checkpoint=workflow_pack_task_flow_checkpoint(),
            resulting_status=WorkflowPackTaskFlowStatus.RUNNING,
            current_step_id="draft-brief",
            updated_at="2026-04-21T01:02:00Z",
        )


def test_task_flow_service_rejects_unknown_task_flow() -> None:
    with pytest.raises(WorkflowPackTaskFlowNotFoundError):
        record_task_flow_checkpoint(
            task_flow_id="missing-task-flow",
            checkpoint=workflow_pack_task_flow_checkpoint(),
            resulting_status=WorkflowPackTaskFlowStatus.RUNNING,
            current_step_id="draft-brief",
            updated_at="2026-04-21T01:02:00Z",
        )


def test_task_flow_service_rejects_checkpoint_for_undeclared_step() -> None:
    create_task_flow(workflow_pack_task_flow_descriptor())
    checkpoint = workflow_pack_task_flow_checkpoint().model_copy(
        update={"step_id": "undeclared-step"}
    )

    with pytest.raises(ValueError, match="declared task-flow step"):
        record_task_flow_checkpoint(
            task_flow_id="task-flow-001",
            checkpoint=checkpoint,
            resulting_status=WorkflowPackTaskFlowStatus.RUNNING,
            current_step_id="draft-brief",
            updated_at="2026-04-21T01:02:00Z",
        )


def test_task_flow_service_rejects_active_state_without_current_step() -> None:
    create_task_flow(workflow_pack_task_flow_descriptor())

    with pytest.raises(ValueError, match="active or waiting task flows require current_step_id"):
        record_task_flow_checkpoint(
            task_flow_id="task-flow-001",
            checkpoint=workflow_pack_task_flow_checkpoint(),
            resulting_status=WorkflowPackTaskFlowStatus.RUNNING,
            current_step_id=None,
            updated_at="2026-04-21T01:02:00Z",
        )


def test_task_flow_service_survives_sqlalchemy_repository_restart(tmp_path: Path) -> None:
    settings.workflow_pack_task_flow_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'workflow-pack-task-flow-restart.db'}"
    upgrade_database_to_head(settings.database_url)
    reset_workflow_pack_task_flow_store_cache()

    create_task_flow(workflow_pack_task_flow_descriptor())
    record_task_flow_checkpoint(
        task_flow_id="task-flow-001",
        checkpoint=workflow_pack_task_flow_checkpoint(),
        resulting_status=WorkflowPackTaskFlowStatus.RUNNING,
        current_step_id="draft-brief",
        updated_at="2026-04-21T01:01:00Z",
    )

    reset_workflow_pack_task_flow_store_cache()

    reloaded = get_task_flow("task-flow-001")
    assert reloaded is not None
    assert reloaded.flow_status == WorkflowPackTaskFlowStatus.RUNNING
    assert reloaded.checkpoint_refs == ["checkpoint-001"]
    assert [
        checkpoint.checkpoint_id for checkpoint in list_task_flow_checkpoints("task-flow-001")
    ] == ["checkpoint-001"]
