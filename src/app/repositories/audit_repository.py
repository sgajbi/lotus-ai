from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.contracts.audit_access import AuditAccessEvent, AuditReadScope
from app.contracts.audit import AuditRecordResponse


class AuditRepository(Protocol):
    def save(self, record: AuditRecordResponse) -> None:
        """Persist an audit record."""

    def get(self, request_id: str, *, scope: AuditReadScope) -> AuditRecordResponse | None:
        """Fetch a previously persisted audit record."""

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
        """List persisted audit records using bounded filters."""

    def save_access_event(self, event: AuditAccessEvent) -> None:
        """Persist an identifier-minimized audit-read access event."""

    def list_access_events(self, *, limit: int = 100) -> Sequence[AuditAccessEvent]:
        """List recent audit-read access events for bounded verification and support."""
