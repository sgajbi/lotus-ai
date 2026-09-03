from __future__ import annotations

from collections.abc import Sequence

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
    ) -> list[WorkflowPackTaskFlowRecord]:
        records = [
            record
            for record in self._task_flows.values()
            if (workflow_pack_id is None or record.descriptor.workflow_pack_id == workflow_pack_id)
            and (caller is None or record.descriptor.caller == caller)
            and (tenant_id is None or record.descriptor.tenant_id == tenant_id)
            and (workflow_surface is None or record.descriptor.workflow_surface == workflow_surface)
            and (flow_status is None or record.descriptor.flow_status.value == flow_status)
            and (
                supportability_status is None
                or record.descriptor.supportability_status.value == supportability_status
            )
        ]
        records.sort(
            key=lambda record: (
                record.descriptor.updated_at,
                record.descriptor.created_at,
                record.descriptor.task_flow_id,
            ),
            reverse=True,
        )
        return deepcopy(records[: max(limit, 0)])

    def list_task_flows_by_run_ref(
        self, *, run_id: str, limit: int
    ) -> list[WorkflowPackTaskFlowRecord]:
        records = [
            record for record in self._task_flows.values() if run_id in record.descriptor.run_refs
        ]
        records.sort(
            key=lambda record: (
                record.descriptor.updated_at,
                record.descriptor.created_at,
                record.descriptor.task_flow_id,
            ),
            reverse=True,
        )
        return deepcopy(records[: max(limit, 0)])

    def get_task_flow(self, *, task_flow_id: str) -> WorkflowPackTaskFlowRecord | None:
        record = self._task_flows.get(task_flow_id)
        if record is None:
            return None
        return deepcopy(record)

    def save_task_flow(self, record: WorkflowPackTaskFlowRecord) -> None:
        self._task_flows[record.descriptor.task_flow_id] = deepcopy(record)

    def delete_task_flows_with_checkpoints(self, task_flow_ids: Sequence[str]) -> tuple[int, int]:
        flows = checkpoints = 0
        wanted = set(task_flow_ids)
        for task_flow_id in task_flow_ids:
            if self._task_flows.pop(task_flow_id, None) is not None:
                flows += 1
        for checkpoint_id, record in list(self._checkpoints.items()):
            if record.descriptor.task_flow_id in wanted:
                self._checkpoints.pop(checkpoint_id, None)
                checkpoints += 1
        return flows, checkpoints

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
