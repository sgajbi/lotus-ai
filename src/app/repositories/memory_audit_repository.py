from __future__ import annotations

from collections.abc import Sequence
from threading import Lock

from app.contracts.audit import AuditRecordResponse
from app.contracts.data_lifecycle import DataLegalHoldRecord, DataLifecycleEventRecord
from app.contracts.audit_access import (
    AuditAccessEvent,
    AuditReadScope,
    AuditReadScopeMode,
)


class InMemoryAuditRepository:
    def __init__(self) -> None:
        self._records: dict[str, AuditRecordResponse] = {}
        self._access_events: dict[str, AuditAccessEvent] = {}
        self._lifecycle_events: dict[str, DataLifecycleEventRecord] = {}
        self._legal_holds: dict[str, DataLegalHoldRecord] = {}
        self._lock = Lock()

    def save(self, record: AuditRecordResponse) -> None:
        with self._lock:
            self._records[record.request_id] = record

    def get(self, request_id: str, *, scope: AuditReadScope) -> AuditRecordResponse | None:
        with self._lock:
            record = self._records.get(request_id)
            return record if record is not None and _record_is_in_scope(record, scope) else None

    def list(
        self,
        *,
        caller_app: str | None = None,
        task_id: str | None = None,
        category: str | None = None,
        output_label: str | None = None,
        requested_by: str | None = None,
        scope: AuditReadScope,
        limit: int = 20,
    ) -> list[AuditRecordResponse]:
        with self._lock:
            records = sorted(
                (record for record in self._records.values() if _record_is_in_scope(record, scope)),
                key=lambda record: record.generated_at,
                reverse=True,
            )
            if caller_app is not None:
                records = [record for record in records if record.caller_app == caller_app]
            if task_id is not None:
                records = [record for record in records if record.task_id == task_id]
            if category is not None:
                records = [record for record in records if record.category.value == category]
            if output_label is not None:
                records = [
                    record for record in records if record.output_label.value == output_label
                ]
            if requested_by is not None:
                records = [record for record in records if record.requested_by == requested_by]
            return records[:limit]

    def delete_records(self, request_ids: Sequence[str]) -> int:
        with self._lock:
            deleted = 0
            for request_id in request_ids:
                if self._records.pop(request_id, None) is not None:
                    deleted += 1
            return deleted

    def save_lifecycle_event(self, event: DataLifecycleEventRecord) -> None:
        with self._lock:
            self._lifecycle_events[event.event_id] = event

    def list_lifecycle_events(self, *, limit: int = 100) -> Sequence[DataLifecycleEventRecord]:
        with self._lock:
            events = sorted(
                self._lifecycle_events.values(),
                key=lambda event: event.recorded_at,
                reverse=True,
            )
            return events[:limit]

    def place_legal_hold(self, record: DataLegalHoldRecord) -> None:
        with self._lock:
            self._legal_holds[record.hold_id] = record

    def release_legal_hold(self, *, hold_id: str, released_at: str) -> bool:
        with self._lock:
            hold = self._legal_holds.get(hold_id)
            if hold is None or hold.released_at is not None:
                return False
            self._legal_holds[hold_id] = hold.model_copy(update={"released_at": released_at})
            return True

    def list_active_legal_holds(
        self, *, family_id: str | None = None
    ) -> Sequence[DataLegalHoldRecord]:
        with self._lock:
            return [
                hold
                for hold in self._legal_holds.values()
                if hold.released_at is None and (family_id is None or hold.family_id == family_id)
            ]

    def save_access_event(self, event: AuditAccessEvent) -> None:
        with self._lock:
            self._access_events[event.event_id] = event

    def list_access_events(self, *, limit: int = 100) -> Sequence[AuditAccessEvent]:
        with self._lock:
            events = sorted(
                self._access_events.values(),
                key=lambda event: event.recorded_at,
                reverse=True,
            )
            return events[:limit]


def _record_is_in_scope(record: AuditRecordResponse, scope: AuditReadScope) -> bool:
    if scope.mode == AuditReadScopeMode.ALL_TENANTS:
        return record.tenant_id is not None or scope.include_legacy_unattributed
    return record.tenant_id in scope.tenant_ids
