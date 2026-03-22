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

    def list(
        self,
        *,
        caller_app: str | None = None,
        task_id: str | None = None,
        limit: int = 20,
    ) -> list[AuditRecordResponse]:
        with self._lock:
            records = sorted(
                self._records.values(),
                key=lambda record: record.generated_at,
                reverse=True,
            )
            if caller_app is not None:
                records = [record for record in records if record.caller_app == caller_app]
            if task_id is not None:
                records = [record for record in records if record.task_id == task_id]
            return records[:limit]
