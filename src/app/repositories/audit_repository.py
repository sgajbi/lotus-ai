from __future__ import annotations

from typing import Protocol

from app.contracts.audit import AuditRecordResponse


class AuditRepository(Protocol):
    def save(self, record: AuditRecordResponse) -> None:
        """Persist an audit record."""

    def get(self, request_id: str) -> AuditRecordResponse | None:
        """Fetch a previously persisted audit record."""
