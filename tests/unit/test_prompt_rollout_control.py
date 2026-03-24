from pathlib import Path

from fastapi import HTTPException

from app.config import settings
from app.contracts.evals import EvaluationRunSubmissionRequest
from app.repositories.evaluation_runtime_repository import EvaluationRunRecord
from app.contracts.prompts import (
    PromptControlActionRequest,
    PromptControlActionType,
    PromptLifecycleStatus,
    PromptRolloutSelectionMode,
)
from app.services.evaluation_runtime_store import get_evaluation_runtime_store
from app.services.eval_async_execution import run_next_evaluation_execution_job
from app.services.eval_run_submission_service import submit_evaluation_run
from app.services.prompt_rollout_control import (
    _resolve_transition,
    apply_prompt_control_action,
    build_prompt_control_history,
)
from app.services.prompt_rollout_models import PromptRolloutEventRecord, PromptRolloutStateRecord
from app.services.prompt_runtime import resolve_runtime_prompt_or_raise
from app.services.prompt_store import get_prompt_repository, reset_prompt_store_cache
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


def test_apply_prompt_control_action_rejects_missing_rollout_state(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'prompt-rollout-missing-state.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        prompt_store_mode="sqlalchemy",
        evaluation_runtime_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        _seed_prompt_approval_gate_pass_sqlalchemy()

        try:
            apply_prompt_control_action(
                PromptControlActionRequest(
                    task_id="missing.v1",
                    action_type=PromptControlActionType.PROMOTE_CANDIDATE,
                    candidate_prompt_version="foundation.explain.v2",
                    requested_by="alice@lotus.test",
                    approved_by="bob@lotus.test",
                    reason="Exercise missing rollout state branch",
                )
            )
        except HTTPException as exc:
            assert exc.status_code == 404
            assert "task_id 'missing.v1' was not found" in str(exc.detail)
        else:
            raise AssertionError("Expected missing rollout state to fail")


def test_apply_prompt_control_action_rejects_blocked_or_invalid_promotion_shapes(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'prompt-rollout-invalid-promote.db'}"
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
                    action_type=PromptControlActionType.PROMOTE_CANDIDATE,
                    requested_by="alice@lotus.test",
                    approved_by="bob@lotus.test",
                    reason="Exercise blocked approval-gate branch",
                )
            )
        except HTTPException as exc:
            assert exc.status_code == 409
            assert "RUNTIME_PASS" in str(exc.detail)
        else:
            raise AssertionError("Expected blocked approval gate to fail")

        _seed_prompt_approval_gate_pass_sqlalchemy()

        for request, expected_status, expected_detail in (
            (
                PromptControlActionRequest(
                    task_id="explain.v1",
                    action_type=PromptControlActionType.PROMOTE_CANDIDATE,
                    requested_by="alice@lotus.test",
                    approved_by="bob@lotus.test",
                    reason="Missing candidate version",
                ),
                422,
                "candidate_prompt_version is required",
            ),
            (
                PromptControlActionRequest(
                    task_id="explain.v1",
                    action_type=PromptControlActionType.PROMOTE_CANDIDATE,
                    candidate_prompt_version="foundation.explain.v1",
                    requested_by="alice@lotus.test",
                    approved_by="bob@lotus.test",
                    reason="Same active version",
                ),
                409,
                "already matches the active prompt version",
            ),
            (
                PromptControlActionRequest(
                    task_id="explain.v1",
                    action_type=PromptControlActionType.PROMOTE_CANDIDATE,
                    candidate_prompt_version="missing.version",
                    requested_by="alice@lotus.test",
                    approved_by="bob@lotus.test",
                    reason="Missing candidate prompt",
                ),
                404,
                "was not found",
            ),
        ):
            try:
                apply_prompt_control_action(request)
            except HTTPException as exc:
                assert exc.status_code == expected_status
                assert expected_detail in str(exc.detail)
            else:
                raise AssertionError("Expected invalid prompt promotion request to fail")


def test_apply_prompt_control_action_rejects_non_candidate_prompt_version(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'prompt-rollout-non-candidate.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        prompt_store_mode="sqlalchemy",
        evaluation_runtime_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        _seed_prompt_approval_gate_pass_sqlalchemy()
        repository = get_prompt_repository()
        rollout_state = repository.get_prompt_rollout_state("explain.v1")
        candidate_prompt = repository.get_prompt_version("explain.v1", "foundation.explain.v2")
        assert rollout_state is not None
        assert candidate_prompt is not None
        repository.save_prompt_rollout_transition(
            rollout_state=rollout_state,
            updated_prompts=[
                candidate_prompt.model_copy(
                    update={"lifecycle_status": PromptLifecycleStatus.RETIRED}
                )
            ],
            event=PromptRolloutEventRecord(
                event_id="prompt_evt_non_candidate_state",
                task_id="explain.v1",
                action_type=PromptControlActionType.PROMOTE_CANDIDATE,
                requested_by="alice@lotus.test",
                approved_by="bob@lotus.test",
                reason="Exercise non-candidate lifecycle branch",
                prior_active_prompt_version="foundation.explain.v1",
                resulting_active_prompt_version="foundation.explain.v1",
                prior_candidate_prompt_version=rollout_state.candidate_prompt_version,
                resulting_candidate_prompt_version=rollout_state.candidate_prompt_version,
                recorded_at="2026-03-24T09:00:00Z",
            ),
        )

        try:
            apply_prompt_control_action(
                PromptControlActionRequest(
                    task_id="explain.v1",
                    action_type=PromptControlActionType.PROMOTE_CANDIDATE,
                    candidate_prompt_version="foundation.explain.v2",
                    requested_by="alice@lotus.test",
                    approved_by="bob@lotus.test",
                    reason="Candidate is retired and not governed candidate",
                )
            )
        except HTTPException as exc:
            assert exc.status_code == 409
            assert "is not a governed candidate" in str(exc.detail)
        else:
            raise AssertionError("Expected non-candidate prompt version to fail")


def test_apply_prompt_control_action_rejects_invalid_rollback_shape(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'prompt-rollout-invalid-rollback-shape.db'}"
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
                reason="Promote before testing invalid rollback request",
            )
        )

        try:
            apply_prompt_control_action(
                PromptControlActionRequest(
                    task_id="explain.v1",
                    action_type=PromptControlActionType.ROLLBACK_TO_PREVIOUS_ACTIVE,
                    candidate_prompt_version="foundation.explain.v2",
                    requested_by="alice@lotus.test",
                    approved_by="bob@lotus.test",
                    reason="Rollback must not accept candidate version",
                )
            )
        except HTTPException as exc:
            assert exc.status_code == 422
            assert "must be omitted" in str(exc.detail)
        else:
            raise AssertionError("Expected invalid rollback request shape to fail")


def test_resolve_transition_rejects_unsupported_action_type() -> None:
    request = PromptControlActionRequest(
        task_id="explain.v1",
        action_type=PromptControlActionType.PROMOTE_CANDIDATE,
        candidate_prompt_version="foundation.explain.v2",
        requested_by="alice@lotus.test",
        approved_by="bob@lotus.test",
        reason="Exercise unsupported action branch",
    ).model_copy(update={"action_type": "INVALID"})

    try:
        _resolve_transition(
            rollout_state=PromptRolloutStateRecord(
                task_id="explain.v1",
                active_prompt_version="foundation.explain.v1",
                candidate_prompt_version="foundation.explain.v2",
                previous_active_prompt_version=None,
                rollout_mode=PromptRolloutSelectionMode.GOVERNED_CONTROL_ACTIONS,
                runtime_mutation_enabled=True,
            ),
            request=request,
        )
    except RuntimeError as exc:
        assert "Unsupported prompt control action" in str(exc)
    else:
        raise AssertionError("Expected unsupported prompt control action to fail")


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
