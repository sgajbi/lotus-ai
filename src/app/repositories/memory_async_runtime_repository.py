from __future__ import annotations

from copy import deepcopy

from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
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
