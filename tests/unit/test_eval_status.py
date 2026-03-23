from app.services.eval_status import build_evaluation_runtime_status


def test_evaluation_runtime_status_reports_staged_assets() -> None:
    status = build_evaluation_runtime_status()

    assert status.service == "lotus-ai"
    assert status.delivery_phase == "foundation"
    assert status.manifest_version == "foundation.v1"
    assert status.evidence_category_count == 6
    assert status.staged_fixture_count >= 11
    assert status.documented_fixture_count == 0
    assert status.staged_case_count == 25
    assert [item.seam_id for item in status.seam_coverage] == [
        "async_execution",
        "task_execution",
        "retrieval",
        "provider_execution",
        "safety_policy",
    ]
    assert status.seam_coverage[0].staged_fixture_count == 1
    assert status.seam_coverage[0].staged_case_count == 3
    assert status.seam_coverage[1].staged_fixture_count == 3
    assert status.seam_coverage[1].staged_case_count == 6
    assert status.seam_coverage[3].staged_fixture_count == 5
    assert status.seam_coverage[3].staged_case_count == 12
    assert status.recorded_run_count == 2
    assert status.latest_recorded_run_id == "foundation_eval_2026_03_22_001"
    assert status.latest_recorded_run_status == "RECORDED"
    assert status.evaluation_runner_active is False
