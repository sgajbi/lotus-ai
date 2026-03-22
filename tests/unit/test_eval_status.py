from app.services.eval_status import build_evaluation_runtime_status


def test_evaluation_runtime_status_reports_staged_assets() -> None:
    status = build_evaluation_runtime_status()

    assert status.service == "lotus-ai"
    assert status.delivery_phase == "foundation"
    assert status.manifest_version == "foundation.v1"
    assert status.evidence_category_count == 5
    assert status.staged_fixture_count >= 6
    assert status.documented_fixture_count == 0
    assert status.staged_case_count == 12
    assert status.evaluation_runner_active is False
