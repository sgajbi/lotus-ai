from __future__ import annotations

from app.contracts.workflow_pack_runs import (
    WorkflowPackRunConsumerSupportabilityDescriptor,
    WorkflowPackRunDescriptor,
    WorkflowPackRunSupportabilityStatus,
)
from app.repositories.workflow_pack_run_repository import WorkflowPackRunRecord
from app.services.workflow_pack_run_supportability import (
    has_workflow_pack_run_partial_output,
    is_workflow_pack_run_historical,
    is_workflow_pack_run_review_pending,
    resolve_workflow_pack_run_supportability_status,
)


def build_workflow_pack_run_supportability_descriptor(
    *,
    run: WorkflowPackRunDescriptor,
) -> WorkflowPackRunConsumerSupportabilityDescriptor:
    status = resolve_workflow_pack_run_supportability_status(run)
    review_pending = is_workflow_pack_run_review_pending(run)
    superseded = is_workflow_pack_run_historical(run)
    partial_output_visible = has_workflow_pack_run_partial_output(run)
    return WorkflowPackRunConsumerSupportabilityDescriptor(
        status=status,
        review_pending=review_pending,
        superseded=superseded,
        partial_output_visible=partial_output_visible,
        summary_note=_build_supportability_summary_note(
            status=status,
            review_pending=review_pending,
            superseded_by_run_id=run.superseded_by_run_id,
        ),
    )


def build_workflow_pack_run_supportability_descriptor_from_record(
    *,
    record: WorkflowPackRunRecord,
    map_record,
) -> WorkflowPackRunConsumerSupportabilityDescriptor:
    return build_workflow_pack_run_supportability_descriptor(run=map_record(record))


def _build_supportability_summary_note(
    *,
    status: WorkflowPackRunSupportabilityStatus,
    review_pending: bool,
    superseded_by_run_id: str | None,
) -> str:
    if status is WorkflowPackRunSupportabilityStatus.HISTORICAL:
        return (
            f"This workflow-pack run is historical because replacement run "
            f"`{superseded_by_run_id}` now carries the latest bounded draft posture."
        )
    if review_pending:
        return (
            "This workflow-pack run completed execution but still requires bounded review before downstream use."
        )
    if status is WorkflowPackRunSupportabilityStatus.ACTION_REQUIRED:
        return "This workflow-pack run remains action-required and should be reviewed before downstream use."
    return "This workflow-pack run is currently supportable through the bounded ledger posture."
