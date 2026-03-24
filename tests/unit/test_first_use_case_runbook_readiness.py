from app.services.first_use_case_runbook_readiness import (
    build_first_use_case_runbook_readiness,
)


def test_first_use_case_runbook_readiness_reports_required_operator_paths_ready() -> None:
    readiness = build_first_use_case_runbook_readiness()

    assert readiness.use_case_id == "lotus_performance.analytics_commentary.v1"
    assert readiness.downstream_app == "lotus-performance"
    assert readiness.runbook_ready is True
    assert readiness.required_item_count == 4
    assert readiness.completed_required_item_count == 4
    assert readiness.items[0].runbook_id == "lotus_performance_shared_ownership"
    assert readiness.items[-1].runbook_id == "lotus_performance_unsupported_input_triage"
