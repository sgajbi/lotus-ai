from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EvaluationRunRecord:
    run_id: str
    fixture_id: str
    manifest_version: str
    lifecycle_status: str
    triggered_by: str
    submitted_at: str
    async_job_id: str | None
    latest_message: str
    verdict: str | None
    case_count: int


@dataclass(frozen=True)
class EvaluationRunAttemptRecord:
    attempt_id: str
    run_id: str
    attempt_number: int
    lifecycle_status: str
    started_at: str | None
    completed_at: str | None
    worker_id: str | None
    latest_message: str
    verdict: str | None
    failure_reason: str | None


@dataclass(frozen=True)
class EvaluationCaseResultRecord:
    case_result_id: str
    run_id: str
    attempt_id: str
    case_id: str
    fixture_id: str
    outcome: str
    summary: str
    evidence_refs: list[str]
    artifact_ids: list[str]
    recorded_at: str


class EvaluationRuntimeRepository(Protocol):
    def list_runs(self) -> list[EvaluationRunRecord]:
        """List all persisted evaluation runs."""

    def get_run(self, *, run_id: str) -> EvaluationRunRecord | None:
        """Fetch one persisted evaluation run."""

    def save_run(self, record: EvaluationRunRecord) -> None:
        """Persist one evaluation run."""

    def list_attempts(self, *, run_id: str) -> list[EvaluationRunAttemptRecord]:
        """List persisted attempts for one evaluation run."""

    def save_attempt(self, record: EvaluationRunAttemptRecord) -> None:
        """Persist one evaluation run attempt."""

    def get_attempt(self, *, attempt_id: str) -> EvaluationRunAttemptRecord | None:
        """Fetch one persisted evaluation run attempt."""

    def list_case_results(self, *, run_id: str) -> list[EvaluationCaseResultRecord]:
        """List persisted case outcomes for one evaluation run."""

    def save_case_result(self, record: EvaluationCaseResultRecord) -> None:
        """Persist one evaluation case result."""
