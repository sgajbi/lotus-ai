from pathlib import Path

from app.repositories.evaluation_runtime_repository import (
    EvaluationCaseResultRecord,
    EvaluationRunAttemptRecord,
    EvaluationRunRecord,
)
from app.repositories.sqlalchemy_evaluation_runtime_repository import (
    SqlAlchemyEvaluationRuntimeRepository,
)
from tests.support.migration_runner import upgrade_database_to_head


def test_sqlalchemy_evaluation_runtime_repository_round_trip(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-eval-runtime.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyEvaluationRuntimeRepository(database_url)

    repository.save_run(
        EvaluationRunRecord(
            run_id="evalrun_001",
            fixture_id="retrieval.answer",
            manifest_version="2026-03-23",
            lifecycle_status="QUEUED",
            triggered_by="operator-a",
            submitted_at="2026-03-23T00:00:00Z",
            async_job_id=None,
            latest_message="Evaluation run queued.",
            verdict=None,
            case_count=2,
        )
    )
    repository.save_attempt(
        EvaluationRunAttemptRecord(
            attempt_id="evalrun_001_attempt_001",
            run_id="evalrun_001",
            attempt_number=1,
            lifecycle_status="QUEUED",
            started_at=None,
            completed_at=None,
            worker_id=None,
            latest_message="Attempt queued.",
            verdict=None,
            failure_reason=None,
        )
    )
    repository.save_case_result(
        EvaluationCaseResultRecord(
            case_result_id="evalcase_001",
            run_id="evalrun_001",
            attempt_id="evalrun_001_attempt_001",
            case_id="retrieval.answer.case_001",
            fixture_id="retrieval.answer",
            outcome="PASS",
            summary="Citations remained bounded and grounded.",
            evidence_refs=["evidence://retrieval.answer.case_001"],
            recorded_at="2026-03-23T00:05:00Z",
        )
    )

    run = repository.get_run(run_id="evalrun_001")
    attempts = repository.list_attempts(run_id="evalrun_001")
    results = repository.list_case_results(run_id="evalrun_001")

    assert run is not None
    assert repository.list_runs() == [run]
    assert len(attempts) == 1
    assert attempts[0].attempt_id == "evalrun_001_attempt_001"
    assert len(results) == 1
    assert results[0].case_id == "retrieval.answer.case_001"


def test_sqlalchemy_evaluation_runtime_repository_returns_empty_results_for_unknown_records(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-eval-runtime.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyEvaluationRuntimeRepository(database_url)

    assert repository.list_runs() == []
    assert repository.get_run(run_id="missing-run") is None
    assert repository.list_attempts(run_id="missing-run") == []
    assert repository.get_attempt(attempt_id="missing-attempt") is None
    assert repository.list_case_results(run_id="missing-run") == []


def test_sqlalchemy_evaluation_runtime_repository_creates_parent_directory_for_sqlite_file(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "nested" / "db" / "lotus-ai-eval-runtime.db"
    database_url = f"sqlite:///{db_path}"

    SqlAlchemyEvaluationRuntimeRepository(database_url)

    assert db_path.parent.is_dir()


def test_sqlalchemy_evaluation_runtime_repository_replaces_attempt_and_case_result_records(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-eval-runtime.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyEvaluationRuntimeRepository(database_url)

    repository.save_attempt(
        EvaluationRunAttemptRecord(
            attempt_id="evalrun_001_attempt_001",
            run_id="evalrun_001",
            attempt_number=1,
            lifecycle_status="QUEUED",
            started_at=None,
            completed_at=None,
            worker_id=None,
            latest_message="Attempt queued.",
            verdict=None,
            failure_reason=None,
        )
    )
    repository.save_attempt(
        EvaluationRunAttemptRecord(
            attempt_id="evalrun_001_attempt_001",
            run_id="evalrun_001",
            attempt_number=1,
            lifecycle_status="COMPLETED",
            started_at="2026-03-23T00:01:00Z",
            completed_at="2026-03-23T00:02:00Z",
            worker_id="worker-a",
            latest_message="Attempt completed.",
            verdict="PASS",
            failure_reason=None,
        )
    )
    repository.save_case_result(
        EvaluationCaseResultRecord(
            case_result_id="evalcase_001",
            run_id="evalrun_001",
            attempt_id="evalrun_001_attempt_001",
            case_id="retrieval.answer.case_001",
            fixture_id="retrieval.answer",
            outcome="FAIL",
            summary="Initial outcome.",
            evidence_refs=["evidence://old"],
            recorded_at="2026-03-23T00:01:00Z",
        )
    )
    repository.save_case_result(
        EvaluationCaseResultRecord(
            case_result_id="evalcase_001",
            run_id="evalrun_001",
            attempt_id="evalrun_001_attempt_001",
            case_id="retrieval.answer.case_001",
            fixture_id="retrieval.answer",
            outcome="PASS",
            summary="Updated outcome.",
            evidence_refs=["evidence://new"],
            recorded_at="2026-03-23T00:02:00Z",
        )
    )

    attempts = repository.list_attempts(run_id="evalrun_001")
    results = repository.list_case_results(run_id="evalrun_001")

    assert len(attempts) == 1
    assert attempts[0].lifecycle_status == "COMPLETED"
    assert len(results) == 1
    assert results[0].outcome == "PASS"

