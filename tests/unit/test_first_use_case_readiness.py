from pathlib import Path

from app.contracts.evals import EvaluationRunSubmissionRequest
from app.services.eval_async_execution import run_next_evaluation_execution_job
from app.services.eval_run_submission_service import submit_evaluation_run
from app.services.first_use_case_readiness import build_first_use_case_readiness
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings


def test_first_use_case_readiness_reports_staged_only_without_runtime_eval_evidence() -> None:
    readiness = build_first_use_case_readiness()

    assert readiness.use_case_id == "lotus_performance.analytics_commentary.v1"
    assert readiness.downstream_app == "lotus-performance"
    assert readiness.readiness_ready is False
    assert readiness.approval_gate.domain_id == "first_use_case_onboarding"
    assert readiness.approval_gate.evidence_state.value == "STAGED_ONLY"
    assert readiness.required_item_count == 4
    assert readiness.completed_required_item_count == 3
    assert readiness.items[0].status == "READY"
    assert readiness.items[1].status == "READY"
    assert readiness.items[2].status == "FOUNDATION_STAGED"
    assert readiness.items[3].status == "READY"


def test_first_use_case_readiness_reports_runtime_pass_after_governed_eval_runs() -> None:
    submit_evaluation_run(
        EvaluationRunSubmissionRequest(
            fixture_id="lotus_performance_first_use_case_examples",
            caller_app="lotus-platform",
            correlation_id="corr-first-use-case-001",
            triggered_by="operator-a",
        )
    )
    run_next_evaluation_execution_job(worker_id="worker-a")

    readiness = build_first_use_case_readiness()

    assert readiness.readiness_ready is True
    assert readiness.completed_required_item_count == readiness.required_item_count
    assert readiness.approval_gate.evidence_state.value == "RUNTIME_PASS"
    assert readiness.items[2].status == "READY"


def test_first_use_case_readiness_uses_sql_seeded_lotus_performance_policy(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'first-use-case-readiness.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        access_control_store_mode="sqlalchemy", database_url=database_url
    ):
        readiness = build_first_use_case_readiness()

    assert readiness.items[0].status == "READY"
