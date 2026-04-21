from __future__ import annotations

from copy import deepcopy

from app.repositories.workflow_pack_queue_event_repository import (
    WorkflowPackQueueEventRecord,
    WorkflowPackQueueEventRepository,
)


class InMemoryWorkflowPackQueueEventRepository(WorkflowPackQueueEventRepository):
    def __init__(self) -> None:
        self._events: dict[str, WorkflowPackQueueEventRecord] = {}

    def list_events(
        self,
        *,
        queue_item_id: str | None = None,
        workflow_pack_id: str | None = None,
        limit: int = 100,
    ) -> list[WorkflowPackQueueEventRecord]:
        records = list(self._events.values())
        if queue_item_id is not None:
            records = [
                record for record in records if record.descriptor.queue_item_id == queue_item_id
            ]
        if workflow_pack_id is not None:
            records = [
                record
                for record in records
                if record.descriptor.workflow_pack_id == workflow_pack_id
            ]
        records.sort(
            key=lambda record: (record.descriptor.recorded_at, record.descriptor.event_id),
            reverse=True,
        )
        return deepcopy(records[:limit])

    def save_event(self, record: WorkflowPackQueueEventRecord) -> None:
        self._events[record.descriptor.event_id] = deepcopy(record)
