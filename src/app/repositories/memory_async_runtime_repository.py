from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from threading import RLock
from typing import Callable

from collections.abc import Sequence
from copy import deepcopy

from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeClaimRecord,
    AsyncRuntimeClaimTransition,
    AsyncRuntimeControlEventRecord,
    AsyncRuntimeJobRecord,
    AsyncRuntimeLeaseRecord,
    AsyncRuntimeRecoveryTransition,
    AsyncRuntimeRepository,
)
from app.repositories.artifact_repository import ArtifactRecord


class InMemoryAsyncRuntimeRepository(AsyncRuntimeRepository):
    def __init__(self) -> None:
        self._jobs: dict[str, AsyncRuntimeJobRecord] = {}
        self._attempts: dict[str, list[AsyncRuntimeAttemptRecord]] = {}
        self._leases_by_job: dict[str, AsyncRuntimeLeaseRecord] = {}
        self._lease_id_to_job: dict[str, str] = {}
        self._control_events: list[AsyncRuntimeControlEventRecord] = []
        self._claim_transition_lock = RLock()

    def list_jobs(self) -> list[AsyncRuntimeJobRecord]:
        return [
            deepcopy(self._jobs[job_id])
            for job_id in sorted(self._jobs, key=lambda item: self._jobs[item].submitted_at)
        ]

    def get_job(self, *, job_id: str) -> AsyncRuntimeJobRecord | None:
        record = self._jobs.get(job_id)
        if record is None:
            return None
        return deepcopy(record)

    def save_job(self, record: AsyncRuntimeJobRecord) -> None:
        self._jobs[record.job_id] = deepcopy(record)

    def list_attempts(self, *, job_id: str) -> list[AsyncRuntimeAttemptRecord]:
        attempts = self._attempts.get(job_id, [])
        return [
            deepcopy(record) for record in sorted(attempts, key=lambda item: item.attempt_number)
        ]

    def save_attempt(self, record: AsyncRuntimeAttemptRecord) -> None:
        attempts = [
            existing
            for existing in self._attempts.get(record.job_id, [])
            if existing.attempt_id != record.attempt_id
        ]
        attempts.append(deepcopy(record))
        self._attempts[record.job_id] = attempts

    def get_attempt(self, *, attempt_id: str) -> AsyncRuntimeAttemptRecord | None:
        for attempts in self._attempts.values():
            for record in attempts:
                if record.attempt_id == attempt_id:
                    return deepcopy(record)
        return None

    def list_leases(self) -> list[AsyncRuntimeLeaseRecord]:
        return [
            deepcopy(self._leases_by_job[job_id])
            for job_id in sorted(
                self._leases_by_job, key=lambda item: self._leases_by_job[item].claimed_at
            )
        ]

    def get_active_lease(self, *, job_id: str) -> AsyncRuntimeLeaseRecord | None:
        record = self._leases_by_job.get(job_id)
        if record is None:
            return None
        return deepcopy(record)

    def save_lease(self, record: AsyncRuntimeLeaseRecord) -> None:
        existing_job_id = self._lease_id_to_job.get(record.lease_id)
        if existing_job_id is not None and existing_job_id != record.job_id:
            self._leases_by_job.pop(existing_job_id, None)
        self._leases_by_job[record.job_id] = deepcopy(record)
        self._lease_id_to_job[record.lease_id] = record.job_id

    def delete_lease(self, *, lease_id: str) -> int:
        job_id = self._lease_id_to_job.pop(lease_id, None)
        if job_id is None:
            return 0
        self._leases_by_job.pop(job_id, None)
        return 1

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
        for job_id in sorted(self._jobs, key=lambda item: self._jobs[item].submitted_at):
            job = self._jobs[job_id]
            if job.lifecycle_status != "QUEUED":
                continue
            if job_types is not None and job.job_type not in job_types:
                continue
            if job_id in self._leases_by_job:
                continue
            attempts = sorted(
                self._attempts.get(job_id, []),
                key=lambda item: item.attempt_number,
            )
            if not attempts:
                continue
            current_attempt = attempts[-1]
            claimed_attempt = AsyncRuntimeAttemptRecord(
                attempt_id=current_attempt.attempt_id,
                job_id=current_attempt.job_id,
                attempt_number=current_attempt.attempt_number,
                lifecycle_status="CLAIMED",
                worker_id=worker_id,
                claimed_at=claimed_at,
                heartbeat_at=heartbeat_at,
                started_at=current_attempt.started_at,
                completed_at=current_attempt.completed_at,
                failure_reason=current_attempt.failure_reason,
                recorded_message=attempt_message,
            )
            claimed_job = replace(
                job,
                lifecycle_status="CLAIMED",
                latest_message=latest_message,
            )
            lease_id = f"{job.job_id}_lease_{current_attempt.attempt_number:03d}"
            lease = AsyncRuntimeLeaseRecord(
                lease_id=lease_id,
                job_id=job.job_id,
                attempt_id=current_attempt.attempt_id,
                worker_id=worker_id,
                claimed_at=claimed_at,
                heartbeat_at=heartbeat_at,
                lease_expires_at=lease_expires_at,
            )
            self.save_attempt(claimed_attempt)
            self.save_job(claimed_job)
            self.save_lease(lease)
            return AsyncRuntimeClaimRecord(
                job=claimed_job,
                attempt=claimed_attempt,
                lease=lease,
            )
        return None

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
        job = self._jobs.get(job_id)
        if job is None or job.lifecycle_status != "QUEUED":
            return None
        if job_id in self._leases_by_job:
            return None
        attempts = sorted(
            self._attempts.get(job_id, []),
            key=lambda item: item.attempt_number,
        )
        if not attempts:
            return None
        current_attempt = attempts[-1]
        claimed_attempt = AsyncRuntimeAttemptRecord(
            attempt_id=current_attempt.attempt_id,
            job_id=current_attempt.job_id,
            attempt_number=current_attempt.attempt_number,
            lifecycle_status="CLAIMED",
            worker_id=worker_id,
            claimed_at=claimed_at,
            heartbeat_at=heartbeat_at,
            started_at=current_attempt.started_at,
            completed_at=current_attempt.completed_at,
            failure_reason=current_attempt.failure_reason,
            recorded_message=attempt_message,
        )
        claimed_job = replace(
            job,
            lifecycle_status="CLAIMED",
            latest_message=latest_message,
        )
        lease = AsyncRuntimeLeaseRecord(
            lease_id=f"{job.job_id}_lease_{current_attempt.attempt_number:03d}",
            job_id=job.job_id,
            attempt_id=current_attempt.attempt_id,
            worker_id=worker_id,
            claimed_at=claimed_at,
            heartbeat_at=heartbeat_at,
            lease_expires_at=lease_expires_at,
        )
        self.save_attempt(claimed_attempt)
        self.save_job(claimed_job)
        self.save_lease(lease)
        return AsyncRuntimeClaimRecord(
            job=claimed_job,
            attempt=claimed_attempt,
            lease=lease,
        )

    def transition_current_claim(
        self,
        *,
        job_id: str,
        worker_id: str,
        attempt_id: str,
        now: str | None,
        job_status: str | None,
        job_message: str | None,
        attempt_status: str | None,
        attempt_message: str,
        failure_reason: str | None,
        lease_expires_at: str | None,
        terminal_artifact: ArtifactRecord | None,
        next_attempt_message: str | None = None,
        now_factory: Callable[[], str] | None = None,
        lease_extension_seconds: int | None = None,
    ) -> AsyncRuntimeClaimTransition | None:
        with self._claim_transition_lock:
            return self._transition_current_claim_locked(
                job_id=job_id,
                worker_id=worker_id,
                attempt_id=attempt_id,
                now=now,
                job_status=job_status,
                job_message=job_message,
                attempt_status=attempt_status,
                attempt_message=attempt_message,
                failure_reason=failure_reason,
                lease_expires_at=lease_expires_at,
                terminal_artifact=terminal_artifact,
                next_attempt_message=next_attempt_message,
                now_factory=now_factory,
                lease_extension_seconds=lease_extension_seconds,
            )

    def _transition_current_claim_locked(
        self,
        *,
        job_id: str,
        worker_id: str,
        attempt_id: str,
        now: str | None,
        job_status: str | None,
        job_message: str | None,
        attempt_status: str | None,
        attempt_message: str,
        failure_reason: str | None,
        lease_expires_at: str | None,
        terminal_artifact: ArtifactRecord | None,
        next_attempt_message: str | None = None,
        now_factory: Callable[[], str] | None = None,
        lease_extension_seconds: int | None = None,
    ) -> AsyncRuntimeClaimTransition | None:
        lease = self._leases_by_job.get(job_id)
        attempt = self.get_attempt(attempt_id=attempt_id)
        job = self._jobs.get(job_id)
        effective_now = now_factory() if now_factory is not None else now
        if effective_now is None:
            raise ValueError("A fresh claim-transition timestamp is required.")
        if (
            lease is None
            or attempt is None
            or job is None
            or lease.worker_id != worker_id
            or lease.attempt_id != attempt_id
            or lease.lease_expires_at <= effective_now
            or job.lifecycle_status not in {"CLAIMED", "RUNNING"}
        ):
            return None

        updated_attempt = replace(
            attempt,
            lifecycle_status=attempt_status or attempt.lifecycle_status,
            heartbeat_at=effective_now,
            started_at=(
                effective_now
                if attempt_status == "RUNNING" and attempt.started_at is None
                else attempt.started_at
            ),
            completed_at=(
                effective_now
                if attempt_status in {"COMPLETED", "FAILED", "ABANDONED"}
                else attempt.completed_at
            ),
            failure_reason=failure_reason,
            recorded_message=attempt_message,
        )
        successor: AsyncRuntimeAttemptRecord | None = None
        if next_attempt_message is not None:
            next_attempt_number = job.attempt_count + 1
            successor = AsyncRuntimeAttemptRecord(
                attempt_id=f"{job.job_id}_attempt_{next_attempt_number:03d}",
                job_id=job.job_id,
                attempt_number=next_attempt_number,
                lifecycle_status="QUEUED",
                worker_id=None,
                claimed_at=None,
                heartbeat_at=None,
                started_at=None,
                completed_at=None,
                failure_reason=None,
                recorded_message=next_attempt_message,
            )
        updated_job = replace(
            job,
            lifecycle_status=job_status or job.lifecycle_status,
            latest_message=job_message or job.latest_message,
            attempt_count=successor.attempt_number if successor is not None else job.attempt_count,
            artifact_ids=(
                [*job.artifact_ids, terminal_artifact.artifact_id]
                if terminal_artifact is not None
                else job.artifact_ids
            ),
        )
        self.save_attempt(updated_attempt)
        self.save_job(updated_job)
        if successor is not None:
            self.save_attempt(successor)
        if lease_expires_at is None and lease_extension_seconds is None:
            self.delete_lease(lease_id=lease.lease_id)
            updated_lease = None
        else:
            renewed_lease_expiry = (
                _extend_lease(effective_now, lease_extension_seconds)
                if lease_extension_seconds is not None
                else lease_expires_at
            )
            assert renewed_lease_expiry is not None
            updated_lease = replace(
                lease,
                heartbeat_at=effective_now,
                lease_expires_at=renewed_lease_expiry,
            )
            self.save_lease(updated_lease)
        return AsyncRuntimeClaimTransition(
            job=deepcopy(updated_job),
            attempt=deepcopy(updated_attempt),
            lease=deepcopy(updated_lease),
            next_attempt=deepcopy(successor),
        )

    def recover_expired_claim(
        self,
        *,
        job_id: str,
        recovered_at: str | None,
        next_attempt_message: str,
        now_factory: Callable[[], str] | None = None,
    ) -> AsyncRuntimeRecoveryTransition | None:
        with self._claim_transition_lock:
            return self._recover_expired_claim_locked(
                job_id=job_id,
                recovered_at=recovered_at,
                next_attempt_message=next_attempt_message,
                now_factory=now_factory,
            )

    def _recover_expired_claim_locked(
        self,
        *,
        job_id: str,
        recovered_at: str | None,
        next_attempt_message: str,
        now_factory: Callable[[], str] | None = None,
    ) -> AsyncRuntimeRecoveryTransition | None:
        lease = self._leases_by_job.get(job_id)
        job = self._jobs.get(job_id)
        effective_recovered_at = now_factory() if now_factory is not None else recovered_at
        if effective_recovered_at is None:
            raise ValueError("A fresh claim-recovery timestamp is required.")
        if (
            lease is None
            or job is None
            or lease.lease_expires_at > effective_recovered_at
            or job.lifecycle_status not in {"CLAIMED", "RUNNING"}
        ):
            return None
        attempt = self.get_attempt(attempt_id=lease.attempt_id)
        if attempt is None:
            return None
        next_attempt_number = job.attempt_count + 1
        next_attempt = AsyncRuntimeAttemptRecord(
            attempt_id=f"{job.job_id}_attempt_{next_attempt_number:03d}",
            job_id=job.job_id,
            attempt_number=next_attempt_number,
            lifecycle_status="QUEUED",
            worker_id=None,
            claimed_at=None,
            heartbeat_at=None,
            started_at=None,
            completed_at=None,
            failure_reason=None,
            recorded_message=next_attempt_message,
        )
        abandoned = replace(
            attempt,
            lifecycle_status="ABANDONED",
            heartbeat_at=lease.heartbeat_at,
            completed_at=effective_recovered_at,
            failure_reason="LEASE_EXPIRED",
            recorded_message="Attempt abandoned after lease expiry and queued for recovery.",
        )
        queued_job = replace(
            job,
            lifecycle_status="QUEUED",
            latest_message=next_attempt.recorded_message,
            attempt_count=next_attempt.attempt_number,
        )
        self.save_attempt(abandoned)
        self.save_attempt(next_attempt)
        self.save_job(queued_job)
        self.delete_lease(lease_id=lease.lease_id)
        return AsyncRuntimeRecoveryTransition(
            job=deepcopy(queued_job),
            abandoned_attempt=deepcopy(abandoned),
            next_attempt=deepcopy(next_attempt),
        )

    def delete_job_records(self, job_ids: Sequence[str]) -> tuple[int, int, int]:
        jobs = attempts = leases = 0
        for job_id in job_ids:
            if self._jobs.pop(job_id, None) is not None:
                jobs += 1
            attempts += len(self._attempts.pop(job_id, []))
            lease = self._leases_by_job.pop(job_id, None)
            if lease is not None:
                self._lease_id_to_job.pop(lease.lease_id, None)
                leases += 1
        return jobs, attempts, leases

    def list_control_events(
        self, *, limit: int = 20, job_id: str | None = None
    ) -> list[AsyncRuntimeControlEventRecord]:
        filtered = [
            deepcopy(record)
            for record in self._control_events
            if job_id is None or record.job_id == job_id
        ]
        filtered.sort(key=lambda item: item.recorded_at, reverse=True)
        return filtered[: max(limit, 1)]

    def delete_control_events(self, event_ids: Sequence[str]) -> int:
        wanted = set(event_ids)
        before = len(self._control_events)
        self._control_events = [r for r in self._control_events if r.event_id not in wanted]
        return before - len(self._control_events)

    def save_control_event(self, record: AsyncRuntimeControlEventRecord) -> None:
        self._control_events = [
            existing for existing in self._control_events if existing.event_id != record.event_id
        ]
        self._control_events.append(deepcopy(record))


def _extend_lease(now: str, seconds: int) -> str:
    return (
        (datetime.fromisoformat(now.replace("Z", "+00:00")) + timedelta(seconds=seconds))
        .isoformat()
        .replace("+00:00", "Z")
    )
