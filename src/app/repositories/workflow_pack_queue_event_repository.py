from __future__ import annotations

from collections.abc import Sequence

from dataclasses import dataclass
from typing import Protocol

from app.contracts.workflow_pack_queue_policies import WorkflowPackQueueEventDescriptor


@dataclass(frozen=True)
class WorkflowPackQueueEventRecord:
    descriptor: WorkflowPackQueueEventDescriptor


class WorkflowPackQueueEventRepository(Protocol):
    def list_events(
        self,
        *,
        queue_item_id: str | None = None,
        workflow_pack_id: str | None = None,
        limit: int | None = 100,
    ) -> list[WorkflowPackQueueEventRecord]: ...

    def save_event(self, record: WorkflowPackQueueEventRecord) -> None: ...

    def delete_events(self, event_ids: Sequence[str]) -> int:
        """Delete queue events by id (lifecycle engine, issue #158 S2c)."""
        ...
