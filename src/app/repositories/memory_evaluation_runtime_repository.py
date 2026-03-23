from __future__ import annotations

from copy import deepcopy

from app.repositories.evaluation_runtime_repository import (
    EvaluationCaseResultRecord,
    EvaluationRunAttemptRecord,
    EvaluationRunRecord,
    EvaluationRuntimeRepository,
)


class InMemoryEvaluationRuntimeRepository(EvaluationRuntimeRepository):
    def __init__(self) -> None:
        self._runs: dict[str, EvaluationRunRecord] = {}
        self._attempts: dict[str, list[EvaluationRunAttemptRecord]] = {}
        self._case_results: dict[str, list[EvaluationCaseResultRecord]] = {}

    def list_runs(self) -> list[EvaluationRunRecord]:
        return [
            deepcopy(self._runs[run_id])
            for run_id in sorted(self._runs, key=lambda item: self._runs[item].submitted_at)
        ]

    def get_run(self, *, run_id: str) -> EvaluationRunRecord | None:
        record = self._runs.get(run_id)
        if record is None:
            return None
        return deepcopy(record)

    def save_run(self, record: EvaluationRunRecord) -> None:
        self._runs[record.run_id] = deepcopy(record)

    def list_attempts(self, *, run_id: str) -> list[EvaluationRunAttemptRecord]:
        return [
            deepcopy(record)
            for record in sorted(
                self._attempts.get(run_id, []),
                key=lambda item: item.attempt_number,
            )
        ]

    def save_attempt(self, record: EvaluationRunAttemptRecord) -> None:
        attempts = [
            existing
            for existing in self._attempts.get(record.run_id, [])
            if existing.attempt_id != record.attempt_id
        ]
        attempts.append(deepcopy(record))
        self._attempts[record.run_id] = attempts

    def get_attempt(self, *, attempt_id: str) -> EvaluationRunAttemptRecord | None:
        for attempts in self._attempts.values():
            for record in attempts:
                if record.attempt_id == attempt_id:
                    return deepcopy(record)
        return None

    def list_case_results(self, *, run_id: str) -> list[EvaluationCaseResultRecord]:
        return [
            deepcopy(record)
            for record in sorted(
                self._case_results.get(run_id, []),
                key=lambda item: item.case_result_id,
            )
        ]

    def save_case_result(self, record: EvaluationCaseResultRecord) -> None:
        results = [
            existing
            for existing in self._case_results.get(record.run_id, [])
            if existing.case_result_id != record.case_result_id
        ]
        results.append(deepcopy(record))
        self._case_results[record.run_id] = results
