from pathlib import Path

from app.repositories.evaluation_runtime_repository import EvaluationRunRecord
from app.contracts.evals import EvaluationRunSubmissionRequest
from fastapi import HTTPException

from app.contracts.prompts import (
    PromptControlActionRequest,
    PromptControlActionType,
    PromptLifecycleStatus,
)
from app.services.eval_async_execution import run_next_evaluation_execution_job
from app.services.eval_run_submission_service import submit_evaluation_run
from app.services.evaluation_runtime_store import (
    get_evaluation_runtime_store,
    reset_evaluation_runtime_store_cache,
)
from app.services.prompt_rollout_control import apply_prompt_control_action
from app.services.prompt_runtime import (
    build_prompt_selection_trace,
    list_active_runtime_prompts,
    list_prompt_rollout_descriptors,
    list_registered_prompts,
    resolve_runtime_prompt_or_raise,
    summarize_prompt_lifecycle_counts,
)
from app.services.prompt_store import reset_prompt_store_cache
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings


def test_resolve_runtime_prompt_or_raise_returns_active_prompt_selection() -> None:
    resolved = resolve_runtime_prompt_or_raise("explain.v1")

    assert resolved.prompt.task_id == "explain.v1"
    assert resolved.prompt.prompt_version == "foundation.explain.v1"
    assert resolved.selection.task_id == "explain.v1"
    assert resolved.selection.selected_for_runtime is True
    assert "governed prompt control actions" in resolved.selection.selection_reason
    assert resolved.selection.rollout_role.value == "ACTIVE"


def test_list_active_runtime_prompts_matches_active_prompt_inventory() -> None:
    active_task_ids = {
        prompt.task_id
        for prompt in list_registered_prompts()
        if prompt.lifecycle_status == PromptLifecycleStatus.ACTIVE
    }

    resolved_task_ids = {resolved.prompt.task_id for resolved in list_active_runtime_prompts()}

    assert resolved_task_ids == active_task_ids


def test_resolve_runtime_prompt_or_raise_rejects_unknown_prompt() -> None:
    try:
        resolve_runtime_prompt_or_raise("missing.v1")
    except HTTPException as exc:
        assert exc.status_code == 404
        assert "No governed prompt rollout state" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException for unknown prompt")


def test_summarize_prompt_lifecycle_counts_matches_registered_inventory() -> None:
    registered_prompts = list_registered_prompts()
    counts = summarize_prompt_lifecycle_counts()

    assert counts.active_prompt_count == sum(
        1
        for prompt in registered_prompts
        if prompt.lifecycle_status == PromptLifecycleStatus.ACTIVE
    )
    assert counts.retired_prompt_count == sum(
        1
        for prompt in registered_prompts
        if prompt.lifecycle_status == PromptLifecycleStatus.RETIRED
    )
    assert counts.candidate_prompt_count == 0


def test_list_prompt_rollout_descriptors_matches_runtime_inventory() -> None:
    rollout_descriptors = list_prompt_rollout_descriptors()

    assert any(descriptor.task_id == "explain.v1" for descriptor in rollout_descriptors)
    assert all(
        descriptor.rollout_mode.value == "GOVERNED_CONTROL_ACTIONS"
        for descriptor in rollout_descriptors
    )
    assert all(descriptor.runtime_mutation_enabled is True for descriptor in rollout_descriptors)
    assert all(descriptor.latest_control_event is None for descriptor in rollout_descriptors)


def test_build_prompt_selection_trace_includes_latest_control_event_after_promotion(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'prompt-trace-promotion.db'}"
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
                reason="Promote explanation prompt",
            )
        )

        trace = build_prompt_selection_trace("explain.v1")

    assert trace.prompt_version == "foundation.explain.v2"
    assert trace.previous_active_prompt_version == "foundation.explain.v1"
    assert trace.latest_control_event is not None
    assert trace.latest_control_event.action_type == PromptControlActionType.PROMOTE_CANDIDATE


def test_prompt_runtime_selection_survives_sql_store_reinitialization(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'prompt-runtime-restart.db'}"
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
                reason="Promote explanation prompt",
            )
        )

        reset_prompt_store_cache()
        reset_evaluation_runtime_store_cache()

        trace = build_prompt_selection_trace("explain.v1")
        rollout = next(
            descriptor
            for descriptor in list_prompt_rollout_descriptors()
            if descriptor.task_id == "explain.v1"
        )

    assert trace.prompt_version == "foundation.explain.v2"
    assert trace.previous_active_prompt_version == "foundation.explain.v1"
    assert trace.latest_control_event is not None
    assert trace.latest_control_event.action_type == PromptControlActionType.PROMOTE_CANDIDATE
    assert rollout.active_prompt_version == "foundation.explain.v2"


def test_prompt_runtime_rollback_lineage_survives_sql_store_reinitialization(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'prompt-runtime-rollback-restart.db'}"
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
                reason="Promote explanation prompt",
            )
        )
        apply_prompt_control_action(
            PromptControlActionRequest(
                task_id="explain.v1",
                action_type=PromptControlActionType.ROLLBACK_TO_PREVIOUS_ACTIVE,
                requested_by="alice@lotus.test",
                approved_by="bob@lotus.test",
                reason="Restore known-good prompt",
            )
        )

        reset_prompt_store_cache()
        reset_evaluation_runtime_store_cache()

        trace = build_prompt_selection_trace("explain.v1")
        rollout = next(
            descriptor
            for descriptor in list_prompt_rollout_descriptors()
            if descriptor.task_id == "explain.v1"
        )

    assert trace.prompt_version == "foundation.explain.v1"
    assert trace.latest_control_event is not None
    assert trace.latest_control_event.action_type == PromptControlActionType.ROLLBACK_TO_PREVIOUS_ACTIVE
    assert rollout.active_prompt_version == "foundation.explain.v1"
    assert rollout.candidate_prompt_version == "foundation.explain.v2"
    assert rollout.latest_control_event is not None
    assert rollout.latest_control_event.action_type == PromptControlActionType.ROLLBACK_TO_PREVIOUS_ACTIVE


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
                run_id=f"runtime_prompt_sql_{fixture_id}",
                fixture_id=fixture_id,
                manifest_version="foundation.v1",
                lifecycle_status="COMPLETED",
                triggered_by="operator-a",
                submitted_at="2026-03-24T09:00:00Z",
                async_job_id=f"async_prompt_sql_{fixture_id}",
                latest_message="Prompt rollout approval fixture passed.",
                verdict="PASS",
                case_count=1,
            )
        )
