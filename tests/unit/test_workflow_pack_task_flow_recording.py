from __future__ import annotations

import pytest

from app.contracts.workflow_pack_runs import (
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
)
from app.contracts.workflow_pack_task_flows import (
    WorkflowPackTaskFlowCheckpointTransition,
    WorkflowPackTaskFlowStatus,
)
from app.contracts.workflow_packs import WorkflowPackRegistrationDescriptor
from app.services.task_execution_models import TaskExecutionContext
from app.services.workflow_pack_registry import get_workflow_pack_registration
from app.services.workflow_pack_task_flow_recording import (
    TASK_FLOW_EXECUTION_STEP_ID,
    build_workflow_pack_task_flow_id,
    record_task_flow_for_workflow_pack_run,
)
from app.services.workflow_pack_task_flow_service import list_task_flow_checkpoints
from tests.support.workflow_pack_fixtures import advisor_brief_task_execution_request
from tests.support.workflow_pack_run_builders import build_workflow_pack_run_descriptor


def _task_execution_context(*, request_id: str) -> TaskExecutionContext:
    return TaskExecutionContext(
        request=advisor_brief_task_execution_request(correlation_id=f"corr-{request_id}"),
        capability=None,  # type: ignore[arg-type]
        authorization=None,  # type: ignore[arg-type]
        prompt=None,  # type: ignore[arg-type]
        prompt_selection=None,  # type: ignore[arg-type]
        safety_outcome=None,  # type: ignore[arg-type]
        request_id=request_id,
        execution_started_at="2026-04-21T01:00:00Z",
    )


def _advisor_brief_registration() -> WorkflowPackRegistrationDescriptor:
    registration = get_workflow_pack_registration(
        pack_id="advisor_brief.pack",
        version="v1",
    )
    assert registration is not None
    return registration


def test_record_task_flow_for_workflow_pack_run_links_waiting_review_checkpoint() -> None:
    run = build_workflow_pack_run_descriptor(
        run_id="run-review-001",
        review_state=WorkflowPackRunReviewState.AWAITING_REVIEW,
    )

    task_flow = record_task_flow_for_workflow_pack_run(
        context=_task_execution_context(request_id=run.request_id),
        registration=_advisor_brief_registration(),
        workflow_surface="advisor-brief-workspace",
        workflow_pack_run=run,
    )

    assert task_flow.task_flow_id == build_workflow_pack_task_flow_id(
        pack_family="advisor_brief",
        request_id=run.request_id,
    )
    assert task_flow.flow_status == WorkflowPackTaskFlowStatus.WAITING_FOR_REVIEW
    assert task_flow.current_step_id == TASK_FLOW_EXECUTION_STEP_ID
    assert task_flow.run_refs == [run.run_id]
    assert task_flow.runtime_states[run.run_id] == WorkflowPackRunRuntimeState.COMPLETED
    assert task_flow.review_states[run.run_id] == WorkflowPackRunReviewState.AWAITING_REVIEW
    assert task_flow.authorization_evidence_ref.attributes["workflow_pack_run_id"] == run.run_id
    assert task_flow.readiness_evidence_ref.attributes["registration_ref"] == run.registration_ref

    checkpoints = list_task_flow_checkpoints(task_flow.task_flow_id)
    assert len(checkpoints) == 1
    assert checkpoints[0].transition == WorkflowPackTaskFlowCheckpointTransition.REVIEW_REQUESTED
    assert checkpoints[0].run_id == run.run_id
    assert checkpoints[0].review_ref == run.run_id
    assert checkpoints[0].degraded is False


@pytest.mark.parametrize(
    ("runtime_state", "review_state", "expected_status", "expected_transition", "degraded"),
    [
        (
            WorkflowPackRunRuntimeState.COMPLETED,
            WorkflowPackRunReviewState.NOT_REVIEW_REQUIRED,
            WorkflowPackTaskFlowStatus.COMPLETED,
            WorkflowPackTaskFlowCheckpointTransition.FLOW_COMPLETED,
            False,
        ),
        (
            WorkflowPackRunRuntimeState.FAILED,
            WorkflowPackRunReviewState.NOT_REVIEW_REQUIRED,
            WorkflowPackTaskFlowStatus.FAILED,
            WorkflowPackTaskFlowCheckpointTransition.STEP_FAILED,
            True,
        ),
        (
            WorkflowPackRunRuntimeState.SUPERSEDED,
            WorkflowPackRunReviewState.SUPERSEDED,
            WorkflowPackTaskFlowStatus.SUPERSEDED,
            WorkflowPackTaskFlowCheckpointTransition.FLOW_SUPERSEDED,
            False,
        ),
    ],
)
def test_record_task_flow_for_terminal_run_uses_terminal_checkpoint_posture(
    runtime_state: WorkflowPackRunRuntimeState,
    review_state: WorkflowPackRunReviewState,
    expected_status: WorkflowPackTaskFlowStatus,
    expected_transition: WorkflowPackTaskFlowCheckpointTransition,
    degraded: bool,
) -> None:
    run = build_workflow_pack_run_descriptor(
        run_id=f"run-{expected_status.value.lower()}-001",
        runtime_state=runtime_state,
        review_state=review_state,
    )

    task_flow = record_task_flow_for_workflow_pack_run(
        context=_task_execution_context(request_id=run.request_id),
        registration=_advisor_brief_registration(),
        workflow_surface="advisor-brief-workspace",
        workflow_pack_run=run,
    )

    assert task_flow.flow_status == expected_status
    assert task_flow.current_step_id is None
    assert task_flow.step_statuses[0].checkpoint_refs == [
        f"{task_flow.task_flow_id}_checkpoint_{run.request_id}"
    ]

    checkpoints = list_task_flow_checkpoints(task_flow.task_flow_id)
    assert checkpoints[0].transition == expected_transition
    assert checkpoints[0].degraded is degraded
    assert checkpoints[0].evidence_refs[0].attributes["runtime_state"] == runtime_state.value
    assert checkpoints[0].evidence_refs[0].attributes["review_state"] == review_state.value
