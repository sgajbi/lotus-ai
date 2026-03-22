from app.services.eval_status import build_evaluation_runtime_status


def test_evaluation_runtime_status_reports_staged_assets() -> None:
    status = build_evaluation_runtime_status()

    assert status.service == "lotus-ai"
    assert status.delivery_phase == "foundation"
    assert status.evidence_category_count == 5
    assert status.staged_fixture_count >= 1
    assert status.documented_fixture_count >= 1
    assert status.evaluation_runner_active is False
