from pathlib import Path

from fastapi import HTTPException

from app.config import settings
from app.contracts.access_control import (
    AuthorizationCapabilityType,
    AuthorizationDecision,
    AuthorizationOutcome,
    TenantPolicyMode,
)
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
from tests.support.governed_control import promote_prompt_for_test
import pytest
from pydantic import ValidationError
from app.contracts.prompts import (
    PromptPromotionApprovalRequest,
    PromptPromotionIntentRequest,
)
from app.http.authenticated_caller import AuthenticatedCaller
from app.services.prompt_rollout_control import (
    approve_prompt_promotion,
    request_prompt_promotion,
)
from tests.support.governed_control import GOVERNED_APPROVER, GOVERNED_REQUESTER


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

        response = promote_prompt_for_test(
            task_id="explain.v1",
            candidate_prompt_version="foundation.explain.v2",
            reason="Approve improved explanation candidate",
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
        promote_prompt_for_test(
            task_id="explain.v1",
            candidate_prompt_version="foundation.explain.v2",
            reason="Approve improved explanation candidate",
        )

        response = apply_prompt_control_action(
            PromptControlActionRequest(
                task_id="explain.v1",
                action_type=PromptControlActionType.ROLLBACK_TO_PREVIOUS_ACTIVE,
                caller_app="lotus-platform",
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
                    caller_app="lotus-platform",
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
        promote_prompt_for_test(
            task_id="explain.v1",
            candidate_prompt_version="foundation.explain.v2",
            reason="Attempt promotion without runtime-backed prompt evidence",
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
            promote_prompt_for_test(
                task_id="explain.v1",
                candidate_prompt_version="foundation.explain.v2",
                reason="Attempt promotion without durable runtime-backed prompt evidence",
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
            promote_prompt_for_test(
                task_id="missing.v1",
                candidate_prompt_version="foundation.explain.v2",
                reason="Exercise missing rollout state branch",
            )
        except HTTPException as exc:
            assert exc.status_code == 404
            assert "task_id 'missing.v1' was not found" in str(exc.detail)
        else:
            raise AssertionError("Expected missing rollout state to fail")


def test_promotion_request_dry_runs_the_transition_and_refuses_invalid_shapes(
    tmp_path: Path,
) -> None:
    """The request step validates the promotion is currently executable before
    parking a pending action, so every refusal the old single call produced
    still fires - now before anything is recorded (issue #157)."""

    database_url = f"sqlite:///{tmp_path / 'prompt-rollout-invalid-promote.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        prompt_store_mode="sqlalchemy",
        evaluation_runtime_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        try:
            request_prompt_promotion(
                PromptPromotionIntentRequest(
                    task_id="explain.v1",
                    candidate_prompt_version="foundation.explain.v2",
                    reason="Exercise blocked approval-gate branch",
                ),
                GOVERNED_REQUESTER,
            )
        except HTTPException as exc:
            assert exc.status_code == 409
            assert "RUNTIME_PASS" in str(exc.detail)
        else:
            raise AssertionError("Expected blocked approval gate to fail")

        _seed_prompt_approval_gate_pass_sqlalchemy()

        # A candidate is required by the contract itself now, not by a branch.
        with pytest.raises(ValidationError):
            PromptPromotionIntentRequest(
                task_id="explain.v1",
                reason="Missing candidate version",
            )  # type: ignore[call-arg]

        for candidate, expected_status, expected_detail in (
            ("foundation.explain.v1", 409, "already matches the active prompt version"),
            ("missing.version", 404, "was not found"),
        ):
            try:
                request_prompt_promotion(
                    PromptPromotionIntentRequest(
                        task_id="explain.v1",
                        candidate_prompt_version=candidate,
                        reason="Invalid promotion shape",
                    ),
                    GOVERNED_REQUESTER,
                )
            except HTTPException as exc:
                assert exc.status_code == expected_status
                assert expected_detail in str(exc.detail)
            else:
                raise AssertionError("Expected invalid promotion request to fail")

        # The single-call route no longer promotes at all: promotion is
        # governed, and the refusal says where to go instead.
        try:
            apply_prompt_control_action(
                PromptControlActionRequest(
                    task_id="explain.v1",
                    action_type=PromptControlActionType.PROMOTE_CANDIDATE,
                    caller_app="lotus-platform",
                    candidate_prompt_version="foundation.explain.v2",
                    requested_by="alice@lotus.test",
                    approved_by="bob@lotus.test",
                    reason="Single-call promotion attempt",
                )
            )
        except HTTPException as exc:
            assert exc.status_code == 409
            assert "governed action" in str(exc.detail)
            assert "promote-requests" in str(exc.detail)
        else:
            raise AssertionError("Expected single-call promotion to be refused")


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
                authorization=_authorization(),
                recorded_at="2026-03-24T09:00:00Z",
            ),
        )

        try:
            promote_prompt_for_test(
                task_id="explain.v1",
                candidate_prompt_version="foundation.explain.v2",
                reason="Candidate is retired and not governed candidate",
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
        promote_prompt_for_test(
            task_id="explain.v1",
            candidate_prompt_version="foundation.explain.v2",
            reason="Promote before testing invalid rollback request",
        )

        try:
            apply_prompt_control_action(
                PromptControlActionRequest(
                    task_id="explain.v1",
                    action_type=PromptControlActionType.ROLLBACK_TO_PREVIOUS_ACTIVE,
                    caller_app="lotus-platform",
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
        caller_app="lotus-platform",
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
            authorization=_authorization(),
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


def test_unauthorized_callers_and_credentials_cannot_promote(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'prompt-rollout-unauthorized.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        prompt_store_mode="sqlalchemy",
        evaluation_runtime_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        _seed_prompt_approval_gate_pass_sqlalchemy()

        # A caller app without the prompt-control capability is refused.
        unauthorized = AuthenticatedCaller(
            caller_app="lotus-manage",
            trust_source="verified_service_jwt",
            credential_key_id="ops-key-alpha",
        )
        try:
            request_prompt_promotion(
                PromptPromotionIntentRequest(
                    task_id="explain.v1",
                    candidate_prompt_version="foundation.explain.v2",
                    reason="Unauthorized promotion attempt",
                ),
                unauthorized,
            )
        except HTTPException as exc:
            assert exc.status_code == 403
            assert "not authorized for prompt control-plane actions" in str(exc.detail)
        else:
            raise AssertionError("Expected unauthorized promotion request to fail")

        # The requester's own credential cannot approve its request, and the
        # active prompt is unchanged afterwards.
        pending = request_prompt_promotion(
            PromptPromotionIntentRequest(
                task_id="explain.v1",
                candidate_prompt_version="foundation.explain.v2",
                reason="Self-approval attempt",
            ),
            GOVERNED_REQUESTER,
        )
        try:
            approve_prompt_promotion(
                PromptPromotionApprovalRequest(
                    task_id="explain.v1",
                    action_id=pending.governed_action.action_id,
                    action_hash=pending.governed_action.action_hash,
                ),
                GOVERNED_REQUESTER,
            )
        except HTTPException as exc:
            assert exc.status_code == 403
            assert "distinct" in str(exc.detail)
        else:
            raise AssertionError("Expected self-approval to be refused")
        state = get_prompt_repository().get_prompt_rollout_state("explain.v1")
        assert state is not None
        assert state.active_prompt_version == "foundation.explain.v1"


def test_a_promotion_approved_against_a_changed_baseline_is_refused(tmp_path: Path) -> None:
    """The hash pins the prior active version. Prompt rollout state genuinely
    can change between request and approval - a rollback, another promotion -
    and an approval reviewed against one baseline must not execute against
    another."""

    database_url = f"sqlite:///{tmp_path / 'prompt-rollout-changed-baseline.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        prompt_store_mode="sqlalchemy",
        evaluation_runtime_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        _seed_prompt_approval_gate_pass_sqlalchemy()
        pending = request_prompt_promotion(
            PromptPromotionIntentRequest(
                task_id="explain.v1",
                candidate_prompt_version="foundation.explain.v2",
                reason="Promotion reviewed against the v1 baseline",
            ),
            GOVERNED_REQUESTER,
        )

        # The baseline changes: the same candidate is promoted and rolled back
        # through governed flows, leaving the rollout state re-derived.
        promote_prompt_for_test(
            task_id="explain.v1",
            candidate_prompt_version="foundation.explain.v2",
            reason="Baseline change",
        )
        apply_prompt_control_action(
            PromptControlActionRequest(
                task_id="explain.v1",
                action_type=PromptControlActionType.ROLLBACK_TO_PREVIOUS_ACTIVE,
                caller_app="lotus-platform",
                requested_by="alice@lotus.test",
                approved_by="bob@lotus.test",
                reason="Baseline restored",
            )
        )

        try:
            approve_prompt_promotion(
                PromptPromotionApprovalRequest(
                    task_id="explain.v1",
                    action_id=pending.governed_action.action_id,
                    action_hash=pending.governed_action.action_hash,
                ),
                GOVERNED_APPROVER,
            )
        except HTTPException as exc:
            # Superseded by the intervening governed promotion of the same
            # target, or refused as changed - either way it cannot execute.
            assert exc.status_code == 409
        else:
            raise AssertionError("Expected approval against a changed baseline to fail")
