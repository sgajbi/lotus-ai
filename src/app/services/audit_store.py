from __future__ import annotations

from threading import Lock

from app.contracts.audit import AuditRecordResponse


class InMemoryAuditStore:
    def __init__(self) -> None:
        self._records: dict[str, AuditRecordResponse] = {}
        self._lock = Lock()

    def save(self, record: AuditRecordResponse) -> None:
        with self._lock:
            self._records[record.request_id] = record

    def get(self, request_id: str) -> AuditRecordResponse | None:
        with self._lock:
            return self._records.get(request_id)


_audit_store = InMemoryAuditStore()


def get_audit_store() -> InMemoryAuditStore:
    return _audit_store
