from __future__ import annotations

from collections.abc import Sequence

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

    def delete_runs_with_dependents(self, run_ids: Sequence[str]) -> tuple[int, int, int]:
        runs = attempts = cases = 0
        for run_id in run_ids:
            if self._runs.pop(run_id, None) is not None:
                runs += 1
            attempts += len(self._attempts.pop(run_id, []))
            cases += len(self._case_results.pop(run_id, []))
        return runs, attempts, cases

    def list_all_case_results(self, *, limit: int) -> list[EvaluationCaseResultRecord]:
        everything = [record for records in self._case_results.values() for record in records]
        everything.sort(key=lambda record: record.recorded_at, reverse=True)
        return [deepcopy(record) for record in everything[:limit]]

    def delete_case_results(self, case_result_ids: Sequence[str]) -> int:
        wanted = set(case_result_ids)
        deleted = 0
        for run_id, records in list(self._case_results.items()):
            kept = [r for r in records if r.case_result_id not in wanted]
            deleted += len(records) - len(kept)
            self._case_results[run_id] = kept
        return deleted

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
