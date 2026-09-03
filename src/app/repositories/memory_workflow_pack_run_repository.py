from __future__ import annotations

from collections.abc import Sequence

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

    def list_runs(self, *, limit: int | None = None) -> list[WorkflowPackRunRecord]:
        run_ids = sorted(
            self._runs,
            key=lambda item: self._runs[item].created_at,
            reverse=limit is not None,
        )
        if limit is not None:
            run_ids = run_ids[: max(limit, 0)]
        return [deepcopy(self._runs[run_id]) for run_id in run_ids]

    def query_runs(
        self,
        *,
        registration_ref: str | None = None,
        pack_id: str | None = None,
        pack_family: str | None = None,
        caller_app: str | None = None,
        tenant_id: str | None = None,
        workflow_surface: str | None = None,
        runtime_state: str | None = None,
        review_state: str | None = None,
        workflow_authority_owner: str | None = None,
        limit: int,
    ) -> list[WorkflowPackRunRecord]:
        records = [
            record
            for record in self._runs.values()
            if (registration_ref is None or record.registration_ref == registration_ref)
            and (pack_id is None or record.pack_id == pack_id)
            and (pack_family is None or record.pack_family == pack_family)
            and (caller_app is None or record.caller_app == caller_app)
            and (tenant_id is None or record.tenant_id == tenant_id)
            and (workflow_surface is None or record.workflow_surface == workflow_surface)
            and (runtime_state is None or record.runtime_state == runtime_state)
            and (review_state is None or record.review_state == review_state)
            and (
                workflow_authority_owner is None
                or record.workflow_authority_owner == workflow_authority_owner
            )
        ]
        records.sort(key=lambda item: item.created_at, reverse=True)
        return deepcopy(records[: max(limit, 0)])

    def get_run(self, *, run_id: str) -> WorkflowPackRunRecord | None:
        record = self._runs.get(run_id)
        if record is None:
            return None
        return deepcopy(record)

    def save_run(self, record: WorkflowPackRunRecord) -> None:
        self._runs[record.run_id] = deepcopy(record)

    def delete_runs_with_events(self, run_ids: Sequence[str]) -> tuple[int, int]:
        runs = events = 0
        for run_id in run_ids:
            if self._runs.pop(run_id, None) is not None:
                runs += 1
            events += len(self._events.pop(run_id, []))
        return runs, events

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
