from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.contracts.audit_access import AuditAccessEvent, AuditReadScope
from app.contracts.audit import AuditRecordResponse
from app.contracts.data_lifecycle import DataLegalHoldRecord, DataLifecycleEventRecord


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

    def delete_records(self, request_ids: Sequence[str]) -> int:
        """Delete audit records by id for the lifecycle engine (issue #158, S2a).

        The engine writes the deletion-evidence event in the same run; this
        method is not exposed on any route.
        """

    def save_lifecycle_event(self, event: DataLifecycleEventRecord) -> None:
        """Persist one append-only deletion-evidence row."""

    def list_lifecycle_events(self, *, limit: int = 100) -> Sequence[DataLifecycleEventRecord]:
        """List deletion evidence, newest first."""

    def place_legal_hold(self, record: DataLegalHoldRecord) -> None:
        """Persist a legal hold; active while released_at is null."""

    def release_legal_hold(self, *, hold_id: str, released_at: str) -> bool:
        """Stamp released_at on one hold; False when no such active hold."""

    def list_active_legal_holds(
        self, *, family_id: str | None = None
    ) -> Sequence[DataLegalHoldRecord]:
        """Active (unreleased) holds, optionally for one family."""

    def save_access_event(self, event: AuditAccessEvent) -> None:
        """Persist an identifier-minimized audit-read access event."""

    def list_access_events(self, *, limit: int = 100) -> Sequence[AuditAccessEvent]:
        """List recent audit-read access events for bounded verification and support."""
