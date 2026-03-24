from pathlib import Path

from fastapi import HTTPException

from app.config import settings
from app.contracts.evals import EvaluationRunSubmissionRequest
from app.repositories.evaluation_runtime_repository import EvaluationRunRecord
from app.contracts.prompts import PromptControlActionRequest, PromptControlActionType
from app.services.evaluation_runtime_store import get_evaluation_runtime_store
from app.services.eval_async_execution import run_next_evaluation_execution_job
from app.services.eval_run_submission_service import submit_evaluation_run
from app.services.prompt_rollout_control import (
    apply_prompt_control_action,
    build_prompt_control_history,
)
from app.services.prompt_runtime import resolve_runtime_prompt_or_raise
from app.services.prompt_store import reset_prompt_store_cache
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings


def test_apply_prompt_control_action_promotes_candidate_and_records_history(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'prompt-rollout-control.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        prompt_store_mode="sqlalchemy",
        evaluation_runtime_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        _seed_prompt_approval_gate_pass_sqlalchemy()

        response = apply_prompt_control_action(
            PromptControlActionRequest(
                task_id="explain.v1",
                action_type=PromptControlActionType.PROMOTE_CANDIDATE,
                candidate_prompt_version="foundation.explain.v2",
                requested_by="alice@lotus.test",
                approved_by="bob@lotus.test",
                reason="Approve improved explanation candidate",
            )
        )

        resolved = resolve_runtime_prompt_or_raise("explain.v1")
        history = build_prompt_control_history(task_id="explain.v1")

        assert response.event.action_type == PromptControlActionType.PROMOTE_CANDIDATE
        assert response.rollout_state.active_prompt_version == "foundation.explain.v2"
        assert response.rollout_state.previous_active_prompt_version == "foundation.explain.v1"
        assert response.rollout_state.candidate_prompt_version is None
        assert resolved.prompt.prompt_version == "foundation.explain.v2"
        assert len(history.latest_events) == 1
        assert history.latest_events[0].resulting_active_prompt_version == "foundation.explain.v2"


def test_apply_prompt_control_action_rolls_back_to_previous_active_version(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'prompt-rollout-rollback.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        prompt_store_mode="sqlalchemy",
        evaluation_runtime_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        _seed_prompt_approval_gate_pass_sqlalchemy()
        apply_prompt_control_action(
            PromptControlActionRequest(
                task_id="explain.v1",
                action_type=PromptControlActionType.PROMOTE_CANDIDATE,
                candidate_prompt_version="foundation.explain.v2",
                requested_by="alice@lotus.test",
                approved_by="bob@lotus.test",
                reason="Approve improved explanation candidate",
            )
        )

        response = apply_prompt_control_action(
            PromptControlActionRequest(
                task_id="explain.v1",
                action_type=PromptControlActionType.ROLLBACK_TO_PREVIOUS_ACTIVE,
                requested_by="alice@lotus.test",
                approved_by="bob@lotus.test",
                reason="Restore known-good prompt",
            )
        )

        resolved = resolve_runtime_prompt_or_raise("explain.v1")

        assert response.rollout_state.active_prompt_version == "foundation.explain.v1"
        assert response.rollout_state.candidate_prompt_version == "foundation.explain.v2"
        assert response.rollout_state.previous_active_prompt_version is None
        assert resolved.prompt.prompt_version == "foundation.explain.v1"


def test_apply_prompt_control_action_rejects_invalid_rollback_without_previous_active(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'prompt-rollout-invalid-rollback.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        prompt_store_mode="sqlalchemy",
        evaluation_runtime_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        try:
            apply_prompt_control_action(
                PromptControlActionRequest(
                    task_id="explain.v1",
                    action_type=PromptControlActionType.ROLLBACK_TO_PREVIOUS_ACTIVE,
                    requested_by="alice@lotus.test",
                    approved_by="bob@lotus.test",
                    reason="Attempt invalid rollback",
                )
            )
        except HTTPException as exc:
            assert exc.status_code == 409
            assert "has no prior active prompt" in str(exc.detail)
        else:
            raise AssertionError("Expected rollback without previous active to fail")


def test_apply_prompt_control_action_blocks_promotion_without_durable_prompt_store() -> None:
    reset_prompt_store_cache()
    settings.prompt_store_mode = "memory"
    settings.evaluation_runtime_store_mode = "memory"

    try:
        apply_prompt_control_action(
            PromptControlActionRequest(
                task_id="explain.v1",
                action_type=PromptControlActionType.PROMOTE_CANDIDATE,
                candidate_prompt_version="foundation.explain.v2",
                requested_by="alice@lotus.test",
                approved_by="bob@lotus.test",
                reason="Attempt promotion without runtime-backed prompt evidence",
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "SQL-backed prompt rollout state" in str(exc.detail)
    else:
        raise AssertionError("Expected promotion without durable prompt store to fail")


def test_apply_prompt_control_action_blocks_promotion_without_durable_evaluation_runtime(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'prompt-rollout-non-durable-eval.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        prompt_store_mode="sqlalchemy",
        evaluation_runtime_store_mode="memory",
        database_url=database_url,
    ):
        try:
            apply_prompt_control_action(
                PromptControlActionRequest(
                    task_id="explain.v1",
                    action_type=PromptControlActionType.PROMOTE_CANDIDATE,
                    candidate_prompt_version="foundation.explain.v2",
                    requested_by="alice@lotus.test",
                    approved_by="bob@lotus.test",
                    reason="Attempt promotion without durable runtime-backed prompt evidence",
                )
            )
        except HTTPException as exc:
            assert exc.status_code == 409
            assert "SQL-backed evaluation runtime evidence" in str(exc.detail)
        else:
            raise AssertionError("Expected promotion without durable evaluation runtime to fail")


def _seed_prompt_approval_gate_pass() -> None:
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


def _seed_prompt_approval_gate_pass_sqlalchemy() -> None:
    for fixture_id in ("prompt_promotion_examples", "prompt_rollback_examples"):
        get_evaluation_runtime_store().save_run(
            EvaluationRunRecord(
                run_id=f"runtime_prompt_control_{fixture_id}",
                fixture_id=fixture_id,
                manifest_version="foundation.v1",
                lifecycle_status="COMPLETED",
                triggered_by="operator-a",
                submitted_at="2026-03-24T09:00:00Z",
                async_job_id=f"async_prompt_control_{fixture_id}",
                latest_message="Prompt rollout approval fixture passed.",
                verdict="PASS",
                case_count=1,
            )
        )
