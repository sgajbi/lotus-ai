from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class WorkflowPackExecutionIdempotencyState(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    INDETERMINATE = "INDETERMINATE"


class WorkflowPackExecutionIdempotencyConflictError(ValueError):
    """Raised when one scoped key is reused for different execution input."""


class WorkflowPackExecutionIdempotencyOwnershipError(RuntimeError):
    """Raised when a non-owner attempts to complete an execution reservation."""


@dataclass(frozen=True)
class WorkflowPackExecutionIdempotencyRecord:
    record_id: str
    caller_app: str
    tenant_scope: str
    idempotency_key: str
    request_fingerprint: str
    state: WorkflowPackExecutionIdempotencyState
    owner_token: str
    response_payload: dict[str, object] | None
    response_checksum_sha256: str | None
    failure_code: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class WorkflowPackExecutionReservation:
    record: WorkflowPackExecutionIdempotencyRecord
    acquired: bool


class WorkflowPackExecutionIdempotencyRepository(Protocol):
    def reserve(
        self, record: WorkflowPackExecutionIdempotencyRecord
    ) -> WorkflowPackExecutionReservation: ...

    def get(self, *, record_id: str) -> WorkflowPackExecutionIdempotencyRecord | None: ...

    def complete(
        self,
        *,
        record_id: str,
        owner_token: str,
        response_payload: dict[str, object],
        response_checksum_sha256: str,
        updated_at: str,
    ) -> WorkflowPackExecutionIdempotencyRecord: ...

    def mark_indeterminate(
        self,
        *,
        record_id: str,
        owner_token: str,
        failure_code: str,
        updated_at: str,
    ) -> WorkflowPackExecutionIdempotencyRecord: ...

    def release(self, *, record_id: str, owner_token: str) -> None: ...
