from __future__ import annotations

from copy import deepcopy

from app.repositories.workflow_pack_run_repository import (
    WorkflowPackRunEventRecord,
    WorkflowPackRunRecord,
    WorkflowPackRunRepository,
)


class InMemoryWorkflowPackRunRepository(WorkflowPackRunRepository):
    def __init__(self) -> None:
        self._runs: dict[str, WorkflowPackRunRecord] = {}
        self._events: dict[str, list[WorkflowPackRunEventRecord]] = {}

    def list_runs(self) -> list[WorkflowPackRunRecord]:
        return [
            deepcopy(self._runs[run_id])
            for run_id in sorted(self._runs, key=lambda item: self._runs[item].created_at)
        ]

    def get_run(self, *, run_id: str) -> WorkflowPackRunRecord | None:
        record = self._runs.get(run_id)
        if record is None:
            return None
        return deepcopy(record)

    def save_run(self, record: WorkflowPackRunRecord) -> None:
        self._runs[record.run_id] = deepcopy(record)

    def list_events(self, *, run_id: str) -> list[WorkflowPackRunEventRecord]:
        events = self._events.get(run_id, [])
        return [deepcopy(event) for event in sorted(events, key=lambda item: item.recorded_at)]

    def save_event(self, record: WorkflowPackRunEventRecord) -> None:
        events = [
            existing
            for existing in self._events.get(record.run_id, [])
            if existing.event_id != record.event_id
        ]
        events.append(deepcopy(record))
        self._events[record.run_id] = events
