from fastapi import HTTPException

from app.contracts.evals import EvaluationRunStatus
from app.services.eval_run_service import build_evaluation_run_catalog, build_evaluation_run_detail


def test_evaluation_run_catalog_reports_recorded_artifacts() -> None:
    catalog = build_evaluation_run_catalog()

    assert catalog.service == "lotus-ai"
    assert catalog.run_count == 2
    assert catalog.latest_run_id == "foundation_eval_2026_03_22_001"
    assert catalog.status_counts[EvaluationRunStatus.RECORDED] == 1
    assert catalog.status_counts[EvaluationRunStatus.SUPERSEDED] == 1
    assert catalog.runs[0].manifest_version == "foundation.v1"
    assert catalog.runs[0].staged_case_count == 20
    assert catalog.runs[1].status == "SUPERSEDED"


def test_evaluation_run_detail_returns_requested_artifact() -> None:
    detail = build_evaluation_run_detail(run_id="foundation_eval_2026_03_22_001")

    assert detail.service == "lotus-ai"
    assert detail.run.run_id == "foundation_eval_2026_03_22_001"
    assert detail.run.seam_coverage[0].seam_id == "task_execution"


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
        assert exc.detail == "Evaluation run artifact 'missing_run' was not found."
    else:
        raise AssertionError("Expected evaluation run lookup to raise HTTPException.")
