from app.services.first_use_case_status import build_first_use_case_runtime_status


def test_first_use_case_runtime_status_describes_lotus_performance_contract() -> None:
    status = build_first_use_case_runtime_status()

    assert status.use_case_id == "lotus_performance.analytics_commentary.v1"
    assert status.downstream_app == "lotus-performance"
    assert status.task_id == "explain.v1"
    assert status.output_label.value == "EXPLANATION_ONLY"
    assert status.contract_hardened is True
    assert status.downstream_contract_fields[0].field_name == "analysis_scope"
    assert any(boundary.owner == "lotus-performance" for boundary in status.ownership_boundaries)
    assert any("does not claim rollout readiness" in line for line in status.status_summary)
