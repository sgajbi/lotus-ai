from __future__ import annotations

from threading import Lock

from app.contracts.audit import AuditRecordResponse


class InMemoryAuditRepository:
    def __init__(self) -> None:
        self._records: dict[str, AuditRecordResponse] = {}
        self._lock = Lock()

    def save(self, record: AuditRecordResponse) -> None:
        with self._lock:
            self._records[record.request_id] = record

    def get(self, request_id: str) -> AuditRecordResponse | None:
        with self._lock:
            return self._records.get(request_id)
