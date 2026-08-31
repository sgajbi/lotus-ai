"""Workflow-pack queue admission lease model (issue #153, S3).

Lives apart from the admission service so the lease repositories can share
the type without importing service logic.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.contracts.artifacts import ArtifactDescriptor
from app.contracts.workflow_pack_queue_policies import (
    WorkflowPackQueueLane,
    WorkflowPackQueueState,
)


@dataclass(frozen=True)
class WorkflowPackQueueAdmissionLease:
    queue_item_id: str
    policy_id: str
    workflow_pack_id: str
    workflow_pack_version: str
    lane: WorkflowPackQueueLane
    state: WorkflowPackQueueState
    admitted_at: str
    caller_app: str | None = None
    correlation_id: str | None = None
    tenant_id: str | None = None
    workflow_surface: str | None = None
    artifact_refs: tuple[ArtifactDescriptor, ...] = ()
