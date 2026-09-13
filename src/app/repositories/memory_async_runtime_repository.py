from __future__ import annotations

from dataclasses import replace

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
        now: str,
        job_status: str | None,
        job_message: str | None,
        attempt_status: str | None,
        attempt_message: str,
        failure_reason: str | None,
        lease_expires_at: str | None,
        terminal_artifact: ArtifactRecord | None,
        next_attempt: AsyncRuntimeAttemptRecord | None = None,
    ) -> AsyncRuntimeClaimTransition | None:
        lease = self._leases_by_job.get(job_id)
        attempt = self.get_attempt(attempt_id=attempt_id)
        job = self._jobs.get(job_id)
        if (
            lease is None
            or attempt is None
            or job is None
            or lease.worker_id != worker_id
            or lease.attempt_id != attempt_id
            or lease.lease_expires_at <= now
            or job.lifecycle_status not in {"CLAIMED", "RUNNING"}
        ):
            return None

        updated_attempt = replace(
            attempt,
            lifecycle_status=attempt_status or attempt.lifecycle_status,
            heartbeat_at=now,
            started_at=(
                now
                if attempt_status == "RUNNING" and attempt.started_at is None
                else attempt.started_at
            ),
            completed_at=(
                now
                if attempt_status in {"COMPLETED", "FAILED", "ABANDONED"}
                else attempt.completed_at
            ),
            failure_reason=failure_reason,
            recorded_message=attempt_message,
        )
        updated_job = replace(
            job,
            lifecycle_status=job_status or job.lifecycle_status,
            latest_message=job_message or job.latest_message,
            artifact_ids=(
                [*job.artifact_ids, terminal_artifact.artifact_id]
                if terminal_artifact is not None
                else job.artifact_ids
            ),
        )
        self.save_attempt(updated_attempt)
        self.save_job(updated_job)
        if next_attempt is not None:
            self.save_attempt(next_attempt)
        if lease_expires_at is None:
            self.delete_lease(lease_id=lease.lease_id)
            updated_lease = None
        else:
            updated_lease = replace(lease, heartbeat_at=now, lease_expires_at=lease_expires_at)
            self.save_lease(updated_lease)
        return AsyncRuntimeClaimTransition(
            job=deepcopy(updated_job),
            attempt=deepcopy(updated_attempt),
            lease=deepcopy(updated_lease),
        )

    def recover_expired_claim(
        self,
        *,
        job_id: str,
        recovered_at: str,
        next_attempt: AsyncRuntimeAttemptRecord,
    ) -> AsyncRuntimeRecoveryTransition | None:
        lease = self._leases_by_job.get(job_id)
        job = self._jobs.get(job_id)
        if (
            lease is None
            or job is None
            or lease.lease_expires_at > recovered_at
            or job.lifecycle_status not in {"CLAIMED", "RUNNING"}
        ):
            return None
        attempt = self.get_attempt(attempt_id=lease.attempt_id)
        if attempt is None or next_attempt.attempt_number != job.attempt_count + 1:
            return None
        abandoned = replace(
            attempt,
            lifecycle_status="ABANDONED",
            heartbeat_at=lease.heartbeat_at,
            completed_at=recovered_at,
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
