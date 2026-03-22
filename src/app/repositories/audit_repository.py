from __future__ import annotations

from typing import Protocol

from app.contracts.audit import AuditRecordResponse


class AuditRepository(Protocol):
    def save(self, record: AuditRecordResponse) -> None:
        """Persist an audit record."""

    def get(self, request_id: str) -> AuditRecordResponse | None:
        """Fetch a previously persisted audit record."""

    def list(
        self,
        *,
        caller_app: str | None = None,
        task_id: str | None = None,
        category: str | None = None,
        output_label: str | None = None,
        requested_by: str | None = None,
        tenant_id: str | None = None,
        limit: int = 20,
    ) -> list[AuditRecordResponse]:
        """List persisted audit records using bounded filters."""
