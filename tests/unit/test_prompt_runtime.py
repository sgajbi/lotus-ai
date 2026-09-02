from pathlib import Path

from app.contracts.access_control import (
    AuthorizationCapabilityType,
    AuthorizationDecision,
    AuthorizationOutcome,
    TenantPolicyMode,
)
from app.repositories.evaluation_runtime_repository import EvaluationRunRecord
from app.prompts.registry import list_prompts as list_seeded_prompts
from app.contracts.evals import EvaluationRunSubmissionRequest
from fastapi import HTTPException
from pytest import MonkeyPatch

from app.contracts.prompts import (
    PromptControlActionRequest,
    PromptControlActionType,
    PromptLifecycleStatus,
    PromptRolloutSelectionMode,
)
from app.services.eval_async_execution import run_next_evaluation_execution_job
from app.services.eval_run_submission_service import submit_evaluation_run
from app.services.evaluation_runtime_store import (
    get_evaluation_runtime_store,
    reset_evaluation_runtime_store_cache,
)
from app.services.prompt_rollout_control import apply_prompt_control_action
from app.services.prompt_rollout_models import PromptRolloutEventRecord, PromptRolloutStateRecord
from app.services.prompt_runtime import (
    build_prompt_selection_trace,
    list_active_runtime_prompts,
    list_prompt_rollout_descriptors,
    list_registered_prompts,
    resolve_runtime_prompt_or_raise,
    summarize_prompt_lifecycle_counts,
)
from app.services.prompt_store import get_prompt_repository, reset_prompt_store_cache
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings
from tests.support.governed_control import promote_prompt_for_test


def _authorization() -> AuthorizationDecision:
    return AuthorizationDecision(
        caller_app="lotus-platform",
        capability_type=AuthorizationCapabilityType.PROMPT_CONTROL,
        outcome=AuthorizationOutcome.ALLOWED,
        allowed=True,
        tenant_policy_mode=TenantPolicyMode.OPTIONAL,
        task_id="explain.v1",
        requested_source_ids=[],
        effective_source_ids=[],
        tenant_id=None,
        summary="Allowed prompt control decision.",
    )


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
        promote_prompt_for_test(
            task_id="explain.v1",
            candidate_prompt_version="foundation.explain.v2",
            reason="Promote explanation prompt",
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
        promote_prompt_for_test(
            task_id="explain.v1",
            candidate_prompt_version="foundation.explain.v2",
            reason="Promote explanation prompt",
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


def test_prompt_runtime_rollback_lineage_survives_sql_store_reinitialization(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'prompt-runtime-rollback-restart.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        prompt_store_mode="sqlalchemy",
        evaluation_runtime_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        _seed_prompt_approval_gate_pass_sqlalchemy()
        promote_prompt_for_test(
            task_id="explain.v1",
            candidate_prompt_version="foundation.explain.v2",
            reason="Promote explanation prompt",
        )
        apply_prompt_control_action(
            PromptControlActionRequest(
                task_id="explain.v1",
                action_type=PromptControlActionType.ROLLBACK_TO_PREVIOUS_ACTIVE,
                caller_app="lotus-platform",
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
    assert (
        trace.latest_control_event.action_type
        == PromptControlActionType.ROLLBACK_TO_PREVIOUS_ACTIVE
    )
    assert rollout.active_prompt_version == "foundation.explain.v1"
    assert rollout.candidate_prompt_version == "foundation.explain.v2"
    assert rollout.latest_control_event is not None
    assert (
        rollout.latest_control_event.action_type
        == PromptControlActionType.ROLLBACK_TO_PREVIOUS_ACTIVE
    )


def test_resolve_runtime_prompt_or_raise_rejects_missing_active_prompt_version(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'prompt-runtime-missing-active.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(prompt_store_mode="sqlalchemy", database_url=database_url):
        repository = get_prompt_repository()
        rollout_state = repository.get_prompt_rollout_state("explain.v1")
        active_prompt = repository.get_prompt_version("explain.v1", "foundation.explain.v1")
        assert rollout_state is not None
        assert active_prompt is not None
        repository.save_prompt_rollout_transition(
            rollout_state=PromptRolloutStateRecord(
                task_id=rollout_state.task_id,
                active_prompt_version="missing.version",
                candidate_prompt_version=rollout_state.candidate_prompt_version,
                previous_active_prompt_version=rollout_state.previous_active_prompt_version,
                rollout_mode=rollout_state.rollout_mode,
                runtime_mutation_enabled=rollout_state.runtime_mutation_enabled,
            ),
            updated_prompts=[active_prompt],
            event=PromptRolloutEventRecord(
                event_id="prompt_evt_runtime_missing_active",
                task_id="explain.v1",
                action_type=PromptControlActionType.PROMOTE_CANDIDATE,
                requested_by="alice@lotus.test",
                approved_by="bob@lotus.test",
                reason="Exercise runtime missing active prompt branch",
                prior_active_prompt_version="foundation.explain.v1",
                resulting_active_prompt_version="missing.version",
                prior_candidate_prompt_version=None,
                resulting_candidate_prompt_version=None,
                authorization=_authorization(),
                recorded_at="2026-03-24T09:00:00Z",
            ),
        )

        try:
            resolve_runtime_prompt_or_raise("explain.v1")
        except HTTPException as exc:
            assert exc.status_code == 409
            assert "missing active prompt version" in str(exc.detail)
        else:
            raise AssertionError("Expected missing active prompt version to fail")


def test_resolve_runtime_prompt_or_raise_rejects_non_active_prompt_definition(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'prompt-runtime-inactive.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(prompt_store_mode="sqlalchemy", database_url=database_url):
        repository = get_prompt_repository()
        rollout_state = repository.get_prompt_rollout_state("explain.v1")
        active_prompt = repository.get_prompt_version("explain.v1", "foundation.explain.v1")
        assert rollout_state is not None
        assert active_prompt is not None
        repository.save_prompt_rollout_transition(
            rollout_state=rollout_state,
            updated_prompts=[
                active_prompt.model_copy(update={"lifecycle_status": PromptLifecycleStatus.RETIRED})
            ],
            event=PromptRolloutEventRecord(
                event_id="prompt_evt_runtime_inactive",
                task_id="explain.v1",
                action_type=PromptControlActionType.PROMOTE_CANDIDATE,
                requested_by="alice@lotus.test",
                approved_by="bob@lotus.test",
                reason="Exercise inactive runtime prompt branch",
                prior_active_prompt_version="foundation.explain.v1",
                resulting_active_prompt_version="foundation.explain.v1",
                prior_candidate_prompt_version=None,
                resulting_candidate_prompt_version=None,
                authorization=_authorization(),
                recorded_at="2026-03-24T09:00:00Z",
            ),
        )

        try:
            resolve_runtime_prompt_or_raise("explain.v1")
        except HTTPException as exc:
            assert exc.status_code == 409
            assert "not active for runtime selection" in str(exc.detail)
        else:
            raise AssertionError("Expected inactive runtime prompt to fail")


def test_build_prompt_selection_trace_rejects_rollout_state_removed_after_resolution(
    monkeypatch: MonkeyPatch,
) -> None:
    class FlakyPromptRepository:
        def __init__(self) -> None:
            self._calls = 0

        def get_prompt_rollout_state(self, task_id: str) -> PromptRolloutStateRecord | None:
            self._calls += 1
            if self._calls == 1:
                return PromptRolloutStateRecord(
                    task_id=task_id,
                    active_prompt_version="foundation.explain.v1",
                    candidate_prompt_version=None,
                    previous_active_prompt_version=None,
                    rollout_mode=PromptRolloutSelectionMode.GOVERNED_CONTROL_ACTIONS,
                    runtime_mutation_enabled=True,
                )
            return None

        def get_prompt_version(self, task_id: str, prompt_version: str) -> object:
            return next(
                prompt
                for prompt in list_seeded_prompts()
                if prompt.task_id == task_id and prompt.prompt_version == prompt_version
            )

        def list_prompt_rollout_events(
            self, task_id: str | None = None, limit: int = 20
        ) -> list[object]:
            return []

    repository = FlakyPromptRepository()
    monkeypatch.setattr("app.services.prompt_runtime.get_prompt_repository", lambda: repository)

    try:
        build_prompt_selection_trace("explain.v1")
    except HTTPException as exc:
        assert exc.status_code == 404
        assert "No governed prompt rollout state" in str(exc.detail)
    else:
        raise AssertionError("Expected missing rollout state during trace build to fail")


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
