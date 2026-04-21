from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.contracts.evidence import ExecutionEvidenceDescriptor
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
    WorkflowPackRunSupportabilityStatus,
)
from app.contracts.workflow_pack_task_flows import (
    WorkflowPackTaskFlowBlockingConditionDescriptor,
    WorkflowPackTaskFlowBlockingConditionStatus,
    WorkflowPackTaskFlowBlockingConditionType,
    WorkflowPackTaskFlowCheckpointDescriptor,
    WorkflowPackTaskFlowCheckpointTransition,
    WorkflowPackTaskFlowDescriptor,
    WorkflowPackTaskFlowHandoffDescriptor,
    WorkflowPackTaskFlowHandoffStatus,
    WorkflowPackTaskFlowReplacementLineageDescriptor,
    WorkflowPackTaskFlowStatus,
    WorkflowPackTaskFlowStepDescriptor,
    WorkflowPackTaskFlowStepStatus,
)
from app.services.workflow_pack_task_flow_contracts import (
    require_task_flow_transition_allowed,
)


def _evidence(evidence_type: str = "TEST_COMMAND") -> ExecutionEvidenceDescriptor:
    return ExecutionEvidenceDescriptor(
        evidence_type=evidence_type,
        summary="Focused task-flow contract proof.",
        attributes={"command": "pytest tests/unit/test_workflow_pack_task_flow_contracts.py"},
    )


def _task_flow(**overrides: object) -> WorkflowPackTaskFlowDescriptor:
    payload = {
        "task_flow_id": "taskflow_advisor_brief_001",
        "workflow_pack_id": "advisor_brief.pack",
        "workflow_pack_version": "1.0.0",
        "tenant_id": "tenant-private-bank-sg",
        "caller": "lotus-workbench",
        "desk_id": "sg-advisory",
        "workflow_surface": "advisor_brief",
        "workflow_authority_owner": "lotus-advise",
        "flow_status": WorkflowPackTaskFlowStatus.WAITING_FOR_REVIEW,
        "current_step_id": "advisor_brief_review",
        "step_statuses": [
            WorkflowPackTaskFlowStepDescriptor(
                step_id="advisor_brief_draft",
                name="Generate advisor brief draft",
                status=WorkflowPackTaskFlowStepStatus.SUCCEEDED,
                run_refs=["workflow_pack_run_advisor_brief_draft_001"],
                checkpoint_refs=["checkpoint_draft_ready"],
            ),
            WorkflowPackTaskFlowStepDescriptor(
                step_id="advisor_brief_review",
                name="Review advisor brief draft",
                status=WorkflowPackTaskFlowStepStatus.BLOCKED,
                review_refs=["workflow_pack_run_advisor_brief_draft_001"],
                blocking_condition_refs=["condition_review_pending"],
            ),
        ],
        "checkpoint_refs": ["checkpoint_draft_ready"],
        "run_refs": ["workflow_pack_run_advisor_brief_draft_001"],
        "review_refs": ["workflow_pack_run_advisor_brief_draft_001"],
        "runtime_states": {
            "workflow_pack_run_advisor_brief_draft_001": WorkflowPackRunRuntimeState.COMPLETED
        },
        "review_states": {
            "workflow_pack_run_advisor_brief_draft_001": WorkflowPackRunReviewState.AWAITING_REVIEW
        },
        "replacement_lineage": [
            WorkflowPackTaskFlowReplacementLineageDescriptor(
                superseded_run_id="workflow_pack_run_advisor_brief_draft_000",
                replacement_run_id="workflow_pack_run_advisor_brief_draft_001",
                review_action_ref="review_action_revise_001",
                reason="Reviewer requested a revised brief with updated suitability evidence.",
            )
        ],
        "blocking_conditions": [
            WorkflowPackTaskFlowBlockingConditionDescriptor(
                condition_id="condition_review_pending",
                condition_type=WorkflowPackTaskFlowBlockingConditionType.WAITING_FOR_REVIEW,
                status=WorkflowPackTaskFlowBlockingConditionStatus.OPEN,
                owner="lotus-workbench",
                message="Advisor brief draft requires banker review before handoff.",
                evidence_refs=[_evidence()],
            )
        ],
        "handoff_refs": [
            WorkflowPackTaskFlowHandoffDescriptor(
                handoff_id="handoff_advisory_review_001",
                owner_service="lotus-advise",
                status=WorkflowPackTaskFlowHandoffStatus.NOT_READY,
                evidence_refs=[_evidence()],
            )
        ],
        "supportability_status": WorkflowPackRunSupportabilityStatus.ACTION_REQUIRED,
        "created_at": "2026-04-21T00:00:00Z",
        "updated_at": "2026-04-21T00:05:00Z",
        "expires_at": "2026-04-22T00:00:00Z",
        "authorization_evidence_ref": _evidence("AUTHORIZATION_DECISION"),
        "readiness_evidence_ref": _evidence("RUNTIME_READINESS"),
    }
    payload.update(overrides)
    return WorkflowPackTaskFlowDescriptor.model_validate(payload)


def test_task_flow_contract_preserves_flow_run_review_and_domain_boundaries() -> None:
    task_flow = _task_flow()

    assert task_flow.flow_status is WorkflowPackTaskFlowStatus.WAITING_FOR_REVIEW
    assert (
        task_flow.runtime_states["workflow_pack_run_advisor_brief_draft_001"]
        is WorkflowPackRunRuntimeState.COMPLETED
    )
    assert (
        task_flow.review_states["workflow_pack_run_advisor_brief_draft_001"]
        is WorkflowPackRunReviewState.AWAITING_REVIEW
    )
    assert task_flow.workflow_authority_owner == "lotus-advise"
    assert task_flow.handoff_refs[0].owner_service == "lotus-advise"
    assert task_flow.supportability_status is WorkflowPackRunSupportabilityStatus.ACTION_REQUIRED


def test_active_task_flow_requires_current_step_to_reference_declared_step() -> None:
    with pytest.raises(ValidationError, match="current_step_id must reference a declared step"):
        _task_flow(current_step_id="missing_step")


def test_active_task_flow_requires_current_step() -> None:
    with pytest.raises(
        ValidationError, match="active or waiting task flows require current_step_id"
    ):
        _task_flow(current_step_id=None)


def test_replacement_lineage_rejects_self_replacement() -> None:
    with pytest.raises(ValidationError, match="replacement_run_id must differ"):
        WorkflowPackTaskFlowReplacementLineageDescriptor(
            superseded_run_id="workflow_pack_run_same",
            replacement_run_id="workflow_pack_run_same",
            reason="Invalid self lineage.",
        )


def test_checkpoint_requires_durable_evidence() -> None:
    with pytest.raises(ValidationError):
        WorkflowPackTaskFlowCheckpointDescriptor(
            checkpoint_id="checkpoint_missing_evidence",
            task_flow_id="taskflow_advisor_brief_001",
            step_id="advisor_brief_draft",
            transition=WorkflowPackTaskFlowCheckpointTransition.STEP_SUCCEEDED,
            actor="lotus-ai.workflow-pack-task-flow",
            recorded_at="2026-04-21T00:05:00Z",
            evidence_refs=[],
            run_id="workflow_pack_run_advisor_brief_draft_001",
            reason="Draft completed.",
        )


def test_transition_validator_allows_revision_loop_and_rejects_terminal_advance() -> None:
    require_task_flow_transition_allowed(
        WorkflowPackTaskFlowStatus.WAITING_FOR_REVIEW,
        WorkflowPackTaskFlowStatus.RUNNING,
    )

    with pytest.raises(ValueError, match="COMPLETED to RUNNING is not allowed"):
        require_task_flow_transition_allowed(
            WorkflowPackTaskFlowStatus.COMPLETED,
            WorkflowPackTaskFlowStatus.RUNNING,
        )
