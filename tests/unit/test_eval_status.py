from app.services.eval_status import build_evaluation_runtime_status


def test_evaluation_runtime_status_reports_staged_assets() -> None:
    status = build_evaluation_runtime_status()

    assert status.service == "lotus-ai"
    assert status.delivery_phase == "foundation"
    assert status.manifest_version == "foundation.v1"
    assert status.evidence_category_count == 6
    assert status.staged_fixture_count >= 14
    assert status.documented_fixture_count == 0
    assert status.staged_case_count == 32
    assert [item.seam_id for item in status.seam_coverage] == [
        "async_execution",
        "task_execution",
        "prompt_rollout",
        "retrieval",
        "provider_execution",
        "safety_execution",
    ]
    assert status.seam_coverage[0].staged_fixture_count == 1
    assert status.seam_coverage[0].staged_case_count == 3
    assert status.seam_coverage[1].staged_fixture_count == 3
    assert status.seam_coverage[1].staged_case_count == 6
    assert status.seam_coverage[2].staged_fixture_count == 2
    assert status.seam_coverage[2].staged_case_count == 2
    assert status.seam_coverage[4].staged_fixture_count == 5
    assert status.seam_coverage[4].staged_case_count == 12
    assert status.seam_coverage[5].staged_fixture_count == 2
    assert status.seam_coverage[5].staged_case_count == 6
    assert [gate.domain_id for gate in status.approval_gates] == [
        "prompt_rollout",
        "retrieval_execution",
        "provider_execution",
        "safety_enforcement",
    ]
    assert status.approval_gates[0].evidence_state.value == "STAGED_ONLY"
    assert status.approval_gates[1].evidence_state.value == "STAGED_ONLY"
    assert status.approval_gates[2].evidence_state.value == "STAGED_ONLY"
    assert status.recorded_run_count == 2
    assert status.runtime_backed_run_count == 0
    assert status.historical_run_count == 2
    assert status.latest_recorded_run_id == "foundation_eval_2026_03_22_001"
    assert status.latest_recorded_run_status == "RECORDED"
    assert status.evaluation_runner_active is True
    assert "approval-gate summaries" in status.message
