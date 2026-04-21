from pathlib import Path

import pytest

from app.config import settings
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunReviewActionType,
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
    WorkflowPackRunSupportabilityStatus,
)
from app.contracts.workflow_pack_task_flows import (
    WorkflowPackTaskFlowCheckpointTransition,
    WorkflowPackTaskFlowStatus,
)
from app.services.workflow_pack_task_flow_service import (
    WorkflowPackTaskFlowNotFoundError,
    create_task_flow,
    get_task_flow,
    list_task_flow_checkpoints,
    record_task_flow_checkpoint,
    synchronize_task_flow_review_action,
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


def test_task_flow_service_rejects_checkpoint_for_different_task_flow() -> None:
    create_task_flow(workflow_pack_task_flow_descriptor())
    checkpoint = workflow_pack_task_flow_checkpoint().model_copy(
        update={"task_flow_id": "different-task-flow"}
    )

    with pytest.raises(ValueError, match="checkpoint task_flow_id must match"):
        record_task_flow_checkpoint(
            task_flow_id="task-flow-001",
            checkpoint=checkpoint,
            resulting_status=WorkflowPackTaskFlowStatus.RUNNING,
            current_step_id="draft-brief",
            updated_at="2026-04-21T01:02:00Z",
        )


def test_task_flow_service_updates_only_checkpointed_step() -> None:
    descriptor = workflow_pack_task_flow_descriptor()
    uncheckpointed_step = descriptor.step_statuses[0].model_copy(
        update={"step_id": "handoff-brief", "name": "Handoff advisor brief"}
    )
    create_task_flow(
        descriptor.model_copy(
            update={"step_statuses": [descriptor.step_statuses[0], uncheckpointed_step]}
        )
    )

    updated = record_task_flow_checkpoint(
        task_flow_id="task-flow-001",
        checkpoint=workflow_pack_task_flow_checkpoint(),
        resulting_status=WorkflowPackTaskFlowStatus.RUNNING,
        current_step_id="draft-brief",
        updated_at="2026-04-21T01:02:00Z",
    )

    assert updated.step_statuses[0].checkpoint_refs == ["checkpoint-001"]
    assert updated.step_statuses[1].step_id == "handoff-brief"
    assert updated.step_statuses[1].checkpoint_refs == []


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


@pytest.mark.parametrize(
    (
        "action_type",
        "initial_status",
        "review_state",
        "supportability_status",
        "expected_status",
        "expected_transition",
    ),
    [
        (
            WorkflowPackRunReviewActionType.ACCEPT,
            WorkflowPackTaskFlowStatus.WAITING_FOR_REVIEW,
            WorkflowPackRunReviewState.ACCEPTED,
            WorkflowPackRunSupportabilityStatus.READY,
            WorkflowPackTaskFlowStatus.COMPLETED,
            WorkflowPackTaskFlowCheckpointTransition.FLOW_COMPLETED,
        ),
        (
            WorkflowPackRunReviewActionType.REJECT,
            WorkflowPackTaskFlowStatus.BLOCKED,
            WorkflowPackRunReviewState.REJECTED,
            WorkflowPackRunSupportabilityStatus.HISTORICAL,
            WorkflowPackTaskFlowStatus.FAILED,
            WorkflowPackTaskFlowCheckpointTransition.STEP_FAILED,
        ),
        (
            WorkflowPackRunReviewActionType.ABANDON,
            WorkflowPackTaskFlowStatus.WAITING_FOR_REVIEW,
            WorkflowPackRunReviewState.ABANDONED,
            WorkflowPackRunSupportabilityStatus.HISTORICAL,
            WorkflowPackTaskFlowStatus.CANCELLED,
            WorkflowPackTaskFlowCheckpointTransition.FLOW_CANCELLED,
        ),
    ],
)
def test_task_flow_review_action_sync_records_terminal_review_posture(
    action_type: WorkflowPackRunReviewActionType,
    initial_status: WorkflowPackTaskFlowStatus,
    review_state: WorkflowPackRunReviewState,
    supportability_status: WorkflowPackRunSupportabilityStatus,
    expected_status: WorkflowPackTaskFlowStatus,
    expected_transition: WorkflowPackTaskFlowCheckpointTransition,
) -> None:
    task_flow = workflow_pack_task_flow_descriptor(
        flow_status=initial_status,
        current_step_id="draft-brief",
    )
    create_task_flow(task_flow)

    synchronize_task_flow_review_action(
        run_id="run-001",
        review_state=review_state,
        supportability_status=supportability_status,
        action_type=action_type,
        reviewed_by="advisor-001",
        reason=f"{action_type.value} during governed review.",
        recorded_at="2026-04-21T01:03:00Z",
    )

    updated = get_task_flow("task-flow-001")
    assert updated is not None
    assert updated.flow_status == expected_status
    assert updated.current_step_id is None
    assert updated.review_states["run-001"] == review_state
    assert updated.supportability_status == supportability_status

    checkpoints = list_task_flow_checkpoints("task-flow-001")
    assert checkpoints[-1].transition == expected_transition
    assert checkpoints[-1].actor == "review:advisor-001"
    assert checkpoints[-1].evidence_refs[0].attributes["action_type"] == action_type.value
    if action_type is WorkflowPackRunReviewActionType.ACCEPT:
        assert updated.handoff_refs[0].status.value == "READY_FOR_HANDOFF"
        assert updated.handoff_refs[0].owner_service == "lotus-advise"
    else:
        assert updated.handoff_refs == []


@pytest.mark.parametrize(
    ("action_type", "expected_transition"),
    [
        (
            WorkflowPackRunReviewActionType.REVISE,
            WorkflowPackTaskFlowCheckpointTransition.REVISION_REQUESTED,
        ),
        (
            WorkflowPackRunReviewActionType.SUPERSEDE,
            WorkflowPackTaskFlowCheckpointTransition.FLOW_SUPERSEDED,
        ),
    ],
)
def test_task_flow_review_action_sync_preserves_replacement_lineage_on_both_flows(
    action_type: WorkflowPackRunReviewActionType,
    expected_transition: WorkflowPackTaskFlowCheckpointTransition,
) -> None:
    source = workflow_pack_task_flow_descriptor(
        flow_status=WorkflowPackTaskFlowStatus.WAITING_FOR_REVIEW,
        current_step_id="draft-brief",
    )
    replacement = workflow_pack_task_flow_descriptor(
        task_flow_id="task-flow-replacement",
        flow_status=WorkflowPackTaskFlowStatus.RUNNING,
        current_step_id="draft-brief",
    ).model_copy(update={"run_refs": ["run-002"]})
    create_task_flow(source)
    create_task_flow(replacement)

    synchronize_task_flow_review_action(
        run_id="run-001",
        review_state=WorkflowPackRunReviewState.SUPERSEDED,
        supportability_status=WorkflowPackRunSupportabilityStatus.HISTORICAL,
        action_type=action_type,
        reviewed_by="advisor-001",
        reason="Replacement run supersedes the prior draft.",
        recorded_at="2026-04-21T01:04:00Z",
        replacement_run_id="run-002",
    )

    updated_source = get_task_flow("task-flow-001")
    updated_replacement = get_task_flow("task-flow-replacement")
    assert updated_source is not None
    assert updated_replacement is not None
    assert updated_source.flow_status == WorkflowPackTaskFlowStatus.SUPERSEDED
    assert updated_source.supportability_status == WorkflowPackRunSupportabilityStatus.HISTORICAL
    assert updated_source.replacement_lineage[0].superseded_run_id == "run-001"
    assert updated_source.replacement_lineage[0].replacement_run_id == "run-002"
    assert updated_source.replacement_lineage[0].review_action_ref == action_type.value
    assert updated_replacement.replacement_lineage == updated_source.replacement_lineage

    checkpoints = list_task_flow_checkpoints("task-flow-001")
    assert checkpoints[-1].transition == expected_transition
