from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.contracts.workflow_pack_task_flows import (
    WorkflowPackTaskFlowCheckpointDescriptor,
    WorkflowPackTaskFlowDescriptor,
)


@dataclass(frozen=True)
class WorkflowPackTaskFlowRecord:
    descriptor: WorkflowPackTaskFlowDescriptor


@dataclass(frozen=True)
class WorkflowPackTaskFlowCheckpointRecord:
    descriptor: WorkflowPackTaskFlowCheckpointDescriptor


class WorkflowPackTaskFlowRepository(Protocol):
    def list_task_flows(self) -> list[WorkflowPackTaskFlowRecord]: ...

    def get_task_flow(self, *, task_flow_id: str) -> WorkflowPackTaskFlowRecord | None: ...

    def save_task_flow(self, record: WorkflowPackTaskFlowRecord) -> None: ...

    def list_checkpoints(
        self, *, task_flow_id: str
    ) -> list[WorkflowPackTaskFlowCheckpointRecord]: ...

    def save_checkpoint(self, record: WorkflowPackTaskFlowCheckpointRecord) -> None: ...
