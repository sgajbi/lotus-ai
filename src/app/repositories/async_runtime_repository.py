from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence
from typing import Protocol

from app.contracts.access_control import AuthorizationDecision


@dataclass(frozen=True)
class AsyncRuntimeJobRecord:
    job_id: str
    job_type: str
    target_id: str | None
    lifecycle_status: str
    submitted_at: str
    caller_app: str
    correlation_id: str
    payload_summary: str
    execution_path: str
    related_evaluation_run_id: str | None
    latest_message: str
    attempt_count: int
    artifact_ids: list[str]
    # Source-owned tenant attribution at creation (issue #291): stamped by
    # the owning submission path when the job carries client-derived content
    # for one tenant; None means platform-owned or pre-attribution history,
    # and is never inferred later.
    tenant_id: str | None = None


@dataclass(frozen=True)
class AsyncRuntimeAttemptRecord:
    attempt_id: str
    job_id: str
    attempt_number: int
    lifecycle_status: str
    worker_id: str | None
    claimed_at: str | None
    heartbeat_at: str | None
    started_at: str | None
    completed_at: str | None
    failure_reason: str | None
    recorded_message: str


@dataclass(frozen=True)
class AsyncRuntimeLeaseRecord:
    lease_id: str
    job_id: str
    attempt_id: str
    worker_id: str
    claimed_at: str
    heartbeat_at: str
    lease_expires_at: str


@dataclass(frozen=True)
class AsyncRuntimeControlEventRecord:
    event_id: str
    job_id: str
    action_type: str
    requested_by: str
    approved_by: str | None
    reason: str
    prior_status: str
    resulting_status: str
    affected_attempt_id: str | None
    authorization: AuthorizationDecision
    recorded_at: str


@dataclass(frozen=True)
class AsyncRuntimeClaimRecord:
    job: AsyncRuntimeJobRecord
    attempt: AsyncRuntimeAttemptRecord
    lease: AsyncRuntimeLeaseRecord


class AsyncRuntimeRepository(Protocol):
    def list_jobs(self) -> list[AsyncRuntimeJobRecord]:
        """List all persisted async jobs."""

    def get_job(self, *, job_id: str) -> AsyncRuntimeJobRecord | None:
        """Fetch one persisted async job."""

    def save_job(self, record: AsyncRuntimeJobRecord) -> None:
        """Persist one async job."""

    def list_attempts(self, *, job_id: str) -> list[AsyncRuntimeAttemptRecord]:
        """List persisted attempts for one async job."""

    def save_attempt(self, record: AsyncRuntimeAttemptRecord) -> None:
        """Persist one async job attempt."""

    def get_attempt(self, *, attempt_id: str) -> AsyncRuntimeAttemptRecord | None:
        """Fetch one persisted async job attempt."""

    def list_leases(self) -> list[AsyncRuntimeLeaseRecord]:
        """List all active async worker leases."""

    def get_active_lease(self, *, job_id: str) -> AsyncRuntimeLeaseRecord | None:
        """Fetch the current active lease for one async job if it exists."""

    def save_lease(self, record: AsyncRuntimeLeaseRecord) -> None:
        """Persist one async worker lease."""

    def delete_lease(self, *, lease_id: str) -> int:
        """Delete one async worker lease and return the number of affected rows."""

    def claim_next_runnable_job(
        self,
        *,
        worker_id: str,
        job_types: tuple[str, ...] | None,
        claimed_at: str,
        heartbeat_at: str,
        lease_expires_at: str,
        latest_message: str,
        attempt_message: str,
    ) -> AsyncRuntimeClaimRecord | None:
        """Atomically claim the next runnable async job if one exists."""

    def claim_runnable_job_by_id(
        self,
        *,
        job_id: str,
        worker_id: str,
        claimed_at: str,
        heartbeat_at: str,
        lease_expires_at: str,
        latest_message: str,
        attempt_message: str,
    ) -> AsyncRuntimeClaimRecord | None:
        """Atomically claim one specific runnable async job if it is still claimable."""

    def delete_job_records(self, job_ids: Sequence[str]) -> tuple[int, int, int]:
        """Delete jobs with their attempts and leases (issue #158, S2a).

        Returns (jobs, attempts, leases) deleted counts; lifecycle-engine
        only, never exposed on a route.
        """

    def list_control_events(
        self, *, limit: int = 20, job_id: str | None = None
    ) -> list[AsyncRuntimeControlEventRecord]:
        """List recent async control-plane events, optionally filtered by job."""

    def delete_control_events(self, event_ids: Sequence[str]) -> int:
        """Delete control events by id for the lifecycle engine (issue #158, S2b)."""

    def save_control_event(self, record: AsyncRuntimeControlEventRecord) -> None:
        """Persist one async control-plane event."""
