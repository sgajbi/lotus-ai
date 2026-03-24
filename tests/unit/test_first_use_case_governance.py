from pathlib import Path

from app.contracts.evals import EvaluationRunSubmissionRequest
from app.services.eval_async_execution import run_next_evaluation_execution_job
from app.services.eval_run_submission_service import submit_evaluation_run
from app.services.first_use_case_governance import build_first_use_case_governance_status
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings


def test_first_use_case_governance_blocks_limited_rollout_in_default_memory_posture() -> None:
    status = build_first_use_case_governance_status()

    assert status.use_case_id == "lotus_performance.analytics_commentary.v1"
    assert status.downstream_app == "lotus-performance"
    assert status.governance_ready is False
    assert status.operational_posture.value == "LIMITED_ROLLOUT_BLOCKED"
    assert status.blocking_area_count == 1
    assert status.readiness.readiness_ready is False
    assert status.runbook_readiness.runbook_ready is True


def test_first_use_case_governance_reports_limited_rollout_ready_when_durable_controls_are_ready(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'first-use-case-governance.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        database_url=database_url,
        access_control_store_mode="sqlalchemy",
        audit_store_mode="sqlalchemy",
        artifact_store_mode="sqlalchemy",
        artifact_object_store_mode="memory",
    ):
        submit_evaluation_run(
            EvaluationRunSubmissionRequest(
                fixture_id="lotus_performance_first_use_case_examples",
                caller_app="lotus-platform",
                correlation_id="corr-first-use-case-governance-001",
                triggered_by="operator-a",
            )
        )
        run_next_evaluation_execution_job(worker_id="worker-a")
        status = build_first_use_case_governance_status()

    assert status.governance_ready is True
    assert status.operational_posture.value == "LIMITED_ROLLOUT_READY"
    assert status.blocking_area_count == 0
    assert status.readiness.readiness_ready is True
    assert status.runbook_readiness.runbook_ready is True
