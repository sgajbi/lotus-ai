from __future__ import annotations

from copy import deepcopy

from app.repositories.workflow_pack_task_flow_repository import (
    WorkflowPackTaskFlowCheckpointRecord,
    WorkflowPackTaskFlowRecord,
    WorkflowPackTaskFlowRepository,
)


class InMemoryWorkflowPackTaskFlowRepository(WorkflowPackTaskFlowRepository):
    def __init__(self) -> None:
        self._task_flows: dict[str, WorkflowPackTaskFlowRecord] = {}
        self._checkpoints: dict[str, WorkflowPackTaskFlowCheckpointRecord] = {}

    def list_task_flows(self) -> list[WorkflowPackTaskFlowRecord]:
        records = sorted(
            self._task_flows.values(),
            key=lambda record: (record.descriptor.created_at, record.descriptor.task_flow_id),
        )
        return deepcopy(records)

    def get_task_flow(self, *, task_flow_id: str) -> WorkflowPackTaskFlowRecord | None:
        record = self._task_flows.get(task_flow_id)
        if record is None:
            return None
        return deepcopy(record)

    def save_task_flow(self, record: WorkflowPackTaskFlowRecord) -> None:
        self._task_flows[record.descriptor.task_flow_id] = deepcopy(record)

    def list_checkpoints(self, *, task_flow_id: str) -> list[WorkflowPackTaskFlowCheckpointRecord]:
        records = [
            record
            for record in self._checkpoints.values()
            if record.descriptor.task_flow_id == task_flow_id
        ]
        records.sort(
            key=lambda record: (record.descriptor.recorded_at, record.descriptor.checkpoint_id)
        )
        return deepcopy(records)

    def save_checkpoint(self, record: WorkflowPackTaskFlowCheckpointRecord) -> None:
        self._checkpoints[record.descriptor.checkpoint_id] = deepcopy(record)
