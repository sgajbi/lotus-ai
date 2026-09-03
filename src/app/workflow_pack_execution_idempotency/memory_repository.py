from __future__ import annotations

from collections.abc import Sequence

from dataclasses import replace
from threading import Lock

from app.workflow_pack_execution_idempotency.repository import (
    WorkflowPackExecutionIdempotencyConflictError,
    WorkflowPackExecutionIdempotencyOwnershipError,
    WorkflowPackExecutionIdempotencyRecord,
    WorkflowPackExecutionIdempotencyState,
    WorkflowPackExecutionReservation,
)


class InMemoryWorkflowPackExecutionIdempotencyRepository:
    def __init__(self) -> None:
        self._records: dict[str, WorkflowPackExecutionIdempotencyRecord] = {}
        self._lock = Lock()

    def reserve(
        self, record: WorkflowPackExecutionIdempotencyRecord
    ) -> WorkflowPackExecutionReservation:
        with self._lock:
            existing = self._records.get(record.record_id)
            if existing is None:
                self._records[record.record_id] = record
                return WorkflowPackExecutionReservation(record=record, acquired=True)
            _ensure_same_fingerprint(existing=existing, proposed=record)
            return WorkflowPackExecutionReservation(record=existing, acquired=False)

    def get(self, *, record_id: str) -> WorkflowPackExecutionIdempotencyRecord | None:
        with self._lock:
            return self._records.get(record_id)

    def complete(
        self,
        *,
        record_id: str,
        owner_token: str,
        response_payload: dict[str, object],
        response_checksum_sha256: str,
        updated_at: str,
    ) -> WorkflowPackExecutionIdempotencyRecord:
        with self._lock:
            current = self._require_owned_in_progress(record_id=record_id, owner_token=owner_token)
            completed = replace(
                current,
                state=WorkflowPackExecutionIdempotencyState.COMPLETED,
                response_payload=response_payload,
                response_checksum_sha256=response_checksum_sha256,
                failure_code=None,
                updated_at=updated_at,
            )
            self._records[record_id] = completed
            return completed

    def mark_indeterminate(
        self,
        *,
        record_id: str,
        owner_token: str,
        failure_code: str,
        updated_at: str,
    ) -> WorkflowPackExecutionIdempotencyRecord:
        with self._lock:
            current = self._require_owned_in_progress(record_id=record_id, owner_token=owner_token)
            indeterminate = replace(
                current,
                state=WorkflowPackExecutionIdempotencyState.INDETERMINATE,
                response_payload=None,
                response_checksum_sha256=None,
                failure_code=failure_code,
                updated_at=updated_at,
            )
            self._records[record_id] = indeterminate
            return indeterminate

    def list_records(self, *, limit: int | None) -> list[WorkflowPackExecutionIdempotencyRecord]:
        with self._lock:
            records = sorted(
                self._records.values(), key=lambda record: record.created_at, reverse=True
            )
            return list(records[:limit])

    def delete_records(self, record_ids: Sequence[str]) -> int:
        with self._lock:
            deleted = 0
            for record_id in record_ids:
                if self._records.pop(record_id, None) is not None:
                    deleted += 1
            return deleted

    def release(self, *, record_id: str, owner_token: str) -> None:
        with self._lock:
            self._require_owned_in_progress(record_id=record_id, owner_token=owner_token)
            del self._records[record_id]

    def _require_owned_in_progress(
        self, *, record_id: str, owner_token: str
    ) -> WorkflowPackExecutionIdempotencyRecord:
        current = self._records.get(record_id)
        if (
            current is None
            or current.owner_token != owner_token
            or current.state is not WorkflowPackExecutionIdempotencyState.IN_PROGRESS
        ):
            raise WorkflowPackExecutionIdempotencyOwnershipError(
                "workflow-pack execution reservation is not owned by this execution"
            )
        return current


def _ensure_same_fingerprint(
    *,
    existing: WorkflowPackExecutionIdempotencyRecord,
    proposed: WorkflowPackExecutionIdempotencyRecord,
) -> None:
    if existing.request_fingerprint != proposed.request_fingerprint:
        raise WorkflowPackExecutionIdempotencyConflictError(
            "idempotency key was reused with different workflow-pack execution input"
        )
