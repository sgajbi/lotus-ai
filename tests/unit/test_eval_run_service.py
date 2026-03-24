from fastapi import HTTPException

from app.contracts.evals import EvaluationRunRecordSource, EvaluationRunStatus
from app.repositories.evaluation_runtime_repository import EvaluationRunRecord
from app.services.eval_run_service import build_evaluation_run_catalog, build_evaluation_run_detail
from app.services.evaluation_runtime_store import get_evaluation_runtime_store


def test_evaluation_run_catalog_reports_recorded_artifacts() -> None:
    catalog = build_evaluation_run_catalog()

    assert catalog.service == "lotus-ai"
    assert catalog.run_count == 2
    assert catalog.runtime_backed_run_count == 0
    assert catalog.historical_run_count == 2
    assert catalog.latest_run_id == "foundation_eval_2026_03_22_001"
    assert catalog.status_counts[EvaluationRunStatus.RECORDED] == 1
    assert catalog.status_counts[EvaluationRunStatus.SUPERSEDED] == 1
    assert catalog.runs[0].manifest_version == "foundation.v1"
    assert catalog.runs[0].staged_case_count == 34
    assert catalog.runs[1].status == "SUPERSEDED"
    assert catalog.runs[0].record_source == EvaluationRunRecordSource.STAGED_ARTIFACT


def test_evaluation_run_detail_returns_requested_artifact() -> None:
    detail = build_evaluation_run_detail(run_id="foundation_eval_2026_03_22_001")

    assert detail.service == "lotus-ai"
    assert detail.run.run_id == "foundation_eval_2026_03_22_001"
    assert detail.run.record_source == EvaluationRunRecordSource.STAGED_ARTIFACT
    assert detail.run.seam_coverage[0].seam_id == "async_execution"


def test_evaluation_run_detail_returns_superseded_artifact() -> None:
    detail = build_evaluation_run_detail(run_id="foundation_eval_2026_03_21_001")

    assert detail.run.run_id == "foundation_eval_2026_03_21_001"
    assert detail.run.status == "SUPERSEDED"
    assert detail.run.seam_coverage[-1].seam_id == "safety_policy"
    assert detail.run.seam_coverage[-1].staged_fixture_count == 0


def test_evaluation_run_detail_raises_not_found_for_unknown_run() -> None:
    try:
        build_evaluation_run_detail(run_id="missing_run")
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Evaluation run 'missing_run' was not found."
    else:
        raise AssertionError("Expected evaluation run lookup to raise HTTPException.")


def test_evaluation_run_catalog_merges_runtime_backed_runs() -> None:
    get_evaluation_runtime_store().save_run(
        EvaluationRunRecord(
            run_id="evalrun_runtime_001",
            fixture_id="retrieval_citation_examples",
            manifest_version="foundation.v1",
            lifecycle_status="QUEUED",
            triggered_by="operator-a",
            submitted_at="2026-03-23T10:00:00Z",
            async_job_id="asyncjob_evaluation_execution_001",
            latest_message="Runtime-backed evaluation submission queued.",
            verdict=None,
            case_count=2,
        )
    )

    catalog = build_evaluation_run_catalog()

    assert catalog.run_count == 3
    assert catalog.runtime_backed_run_count == 1
    assert catalog.historical_run_count == 2
    assert catalog.latest_run_id == "evalrun_runtime_001"
    assert catalog.status_counts[EvaluationRunStatus.QUEUED] == 1
    assert catalog.runs[0].record_source == EvaluationRunRecordSource.RUNTIME_STATE
    assert catalog.runs[0].fixture_id == "retrieval_citation_examples"
    assert catalog.runs[0].async_job_id == "asyncjob_evaluation_execution_001"
    assert catalog.runs[0].seam_coverage[0].seam_id == "retrieval"


def test_evaluation_run_detail_returns_runtime_backed_run() -> None:
    get_evaluation_runtime_store().save_run(
        EvaluationRunRecord(
            run_id="evalrun_runtime_001",
            fixture_id="provider_runtime_examples",
            manifest_version="foundation.v1",
            lifecycle_status="QUEUED",
            triggered_by="operator-a",
            submitted_at="2026-03-23T10:00:00Z",
            async_job_id="asyncjob_evaluation_execution_001",
            latest_message="Runtime-backed evaluation submission queued.",
            verdict=None,
            case_count=2,
        )
    )

    detail = build_evaluation_run_detail(run_id="evalrun_runtime_001")

    assert detail.run.record_source == EvaluationRunRecordSource.RUNTIME_STATE
    assert detail.run.fixture_id == "provider_runtime_examples"
    assert detail.run.seam_coverage[0].seam_id == "provider_execution"
    assert detail.attempts == []
    assert detail.case_results == []
