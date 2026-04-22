from __future__ import annotations

from pydantic import BaseModel, Field

from app.contracts.workflow_pack_queue_policies import WorkflowPackQueueEventDescriptor
from app.contracts.workflow_packs import WorkflowPackExecutionResponse


class WorkflowPackQueueRecoveryExecutionResponse(BaseModel):
    service: str = Field(
        description="Service emitting the workflow-pack queue recovery execution response."
    )
    version: str = Field(description="Current lotus-ai service version.")
    phase: str = Field(description="Current lotus-ai delivery phase.")
    decision_event: WorkflowPackQueueEventDescriptor = Field(
        description="Durable queue event recording the governed retry or replay execution decision."
    )
    execution: WorkflowPackExecutionResponse = Field(
        description="Workflow-pack execution response produced from the retained request snapshot."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of the queue recovery execution posture."
    )
