from __future__ import annotations

from copy import deepcopy

from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeClaimRecord,
    AsyncRuntimeControlEventRecord,
    AsyncRuntimeJobRecord,
    AsyncRuntimeLeaseRecord,
    AsyncRuntimeRepository,
)


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
            for job_id in sorted(self._leases_by_job, key=lambda item: self._leases_by_job[item].claimed_at)
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
            claimed_job = AsyncRuntimeJobRecord(
                job_id=job.job_id,
                job_type=job.job_type,
                target_id=job.target_id,
                lifecycle_status="CLAIMED",
                submitted_at=job.submitted_at,
                caller_app=job.caller_app,
                correlation_id=job.correlation_id,
                payload_summary=job.payload_summary,
                execution_path=job.execution_path,
                related_evaluation_run_id=job.related_evaluation_run_id,
                latest_message=latest_message,
                attempt_count=job.attempt_count,
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

    def save_control_event(self, record: AsyncRuntimeControlEventRecord) -> None:
        self._control_events = [
            existing for existing in self._control_events if existing.event_id != record.event_id
        ]
        self._control_events.append(deepcopy(record))
