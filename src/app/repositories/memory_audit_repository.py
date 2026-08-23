from __future__ import annotations

from collections.abc import Sequence
from threading import Lock

from app.contracts.audit import AuditRecordResponse
from app.contracts.audit_access import (
    AuditAccessEvent,
    AuditReadScope,
    AuditReadScopeMode,
)


class InMemoryAuditRepository:
    def __init__(self) -> None:
        self._records: dict[str, AuditRecordResponse] = {}
        self._access_events: dict[str, AuditAccessEvent] = {}
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
