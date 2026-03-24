from pathlib import Path

from app.contracts.evals import EvaluationRunSubmissionRequest
from app.services.eval_async_execution import run_next_evaluation_execution_job
from app.services.eval_run_submission_service import submit_evaluation_run
from app.services.prompt_activation_readiness import build_prompt_activation_readiness
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings


def test_prompt_activation_readiness_blocks_memory_only_runtime_for_live_activation() -> None:
    readiness = build_prompt_activation_readiness()

    assert readiness.service == "lotus-ai"
    assert readiness.prompt_store_mode == "memory"
    assert readiness.management_mode == "SEEDED_MEMORY"
    assert readiness.activation_ready is False
    assert len(readiness.blocking_findings) == 1
    assert "SQL-backed prompt rollout state" in readiness.blocking_findings[0]
    assert len(readiness.activation_path) == 4


def test_prompt_activation_readiness_remains_blocked_after_prompt_eval_pass_without_durable_stores() -> None:
    for fixture_id in ("prompt_promotion_examples", "prompt_rollback_examples"):
        submit_evaluation_run(
            EvaluationRunSubmissionRequest(
                fixture_id=fixture_id,
                caller_app="lotus-platform",
                correlation_id=f"corr-{fixture_id}",
                triggered_by="operator-a",
            )
        )
        run_next_evaluation_execution_job(worker_id="worker-a")

    readiness = build_prompt_activation_readiness()

    assert readiness.activation_ready is False
    assert len(readiness.blocking_findings) == 1


def test_prompt_activation_readiness_is_ready_with_sql_backed_prompt_and_eval_stores(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'prompt-activation-readiness.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        prompt_store_mode="sqlalchemy",
        evaluation_runtime_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        readiness = build_prompt_activation_readiness()

    assert readiness.activation_ready is True
    assert readiness.blocking_findings == []
