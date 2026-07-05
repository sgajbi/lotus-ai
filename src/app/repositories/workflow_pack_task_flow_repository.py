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

    def query_task_flows(
        self,
        *,
        workflow_pack_id: str | None = None,
        caller: str | None = None,
        tenant_id: str | None = None,
        workflow_surface: str | None = None,
        flow_status: str | None = None,
        supportability_status: str | None = None,
        limit: int,
    ) -> list[WorkflowPackTaskFlowRecord]: ...

    def list_task_flows_by_run_ref(
        self, *, run_id: str, limit: int
    ) -> list[WorkflowPackTaskFlowRecord]: ...

    def get_task_flow(self, *, task_flow_id: str) -> WorkflowPackTaskFlowRecord | None: ...

    def save_task_flow(self, record: WorkflowPackTaskFlowRecord) -> None: ...

    def list_checkpoints(
        self, *, task_flow_id: str
    ) -> list[WorkflowPackTaskFlowCheckpointRecord]: ...

    def save_checkpoint(self, record: WorkflowPackTaskFlowCheckpointRecord) -> None: ...
