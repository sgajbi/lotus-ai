from pathlib import Path

from fastapi import HTTPException

from app.config import settings
from app.contracts.access_control import (
    AuthorizationCapabilityType,
    AuthorizationDecision,
    AuthorizationOutcome,
    TenantPolicyMode,
)
from app.contracts.prompts import PromptControlActionRequest, PromptControlActionType
from app.contracts.evals import EvaluationCaseOutcome
from app.evals.fixture_manifest import EvaluationFixtureRuntimeCase
from app.repositories.evaluation_runtime_repository import EvaluationRunRecord
from app.services.eval_runtime_execution import (
    _apply_prompt_rollback_for_evaluation,
    _apply_prompt_transition_for_evaluation,
    _apply_case_configuration,
    _execute_fixture_case,
)
from app.services.evaluation_runtime_store import get_evaluation_runtime_store
from app.services.prompt_rollout_control import apply_prompt_control_action
from app.services.prompt_rollout_models import PromptRolloutEventRecord, PromptRolloutStateRecord
from app.services.prompt_store import get_prompt_repository
from app.services.provider_operations_store import reset_provider_operations_store_cache
from tests.support.migration_runner import upgrade_database_to_head
from tests.support.runtime_settings import override_runtime_settings


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


def test_execute_fixture_case_reports_failure_for_provider_operations_state_mismatch() -> None:
    summary, outcome, evidence_refs = _execute_fixture_case(
        fixture_id="provider_operations_examples",
        fixture_task_id="provider_operations_examples",
        case=EvaluationFixtureRuntimeCase(
            case_id="provider_ops_mismatch_case",
            summary="Expect the wrong provider operations state.",
            input_payload={},
            expected_payload={"operations_state": "CIRCUIT_OPEN"},
        ),
    )

    assert outcome == EvaluationCaseOutcome.FAIL
    assert "did not match expected runtime evidence" in summary
    assert evidence_refs == ["service://platform/providers/operations-status"]


def test_execute_fixture_case_reports_pass_for_provider_embedding_rejection_case() -> None:
    case = EvaluationFixtureRuntimeCase(
        case_id="live_embedding_mode_requires_complete_configuration",
        summary="Live embedding mode should reject partial credential configuration before execution.",
        input_payload={
            "embedding_provider_mode": "enabled",
            "live_embedding_provider_id": "embeddings.openai",
            "live_embedding_model_id": None,
            "live_embedding_provider_api_key": "secret",
        },
        expected_payload={
            "failure_category": "INVALID_LIVE_CONFIGURATION",
            "expected_outcome": "REJECTION",
        },
    )

    with _apply_case_configuration(case.input_payload):
        summary, outcome, evidence_refs = _execute_fixture_case(
            fixture_id="provider_embedding_examples",
            fixture_task_id="provider.embeddings.v1",
            case=case,
        )

    assert outcome == EvaluationCaseOutcome.PASS
    assert "invalid configuration posture" in summary
    assert evidence_refs == ["service://platform/providers", "service://platform/providers/policy"]


def test_execute_fixture_case_reports_pass_for_provider_embedding_success_case() -> None:
    case = EvaluationFixtureRuntimeCase(
        case_id="live_embedding_execution_returns_vector_metadata",
        summary="Live embedding execution should preserve provider identity and vector metadata when bounded rollout is configured.",
        input_payload={
            "embedding_provider_mode": "enabled",
            "live_embedding_provider_id": "embeddings.openai",
            "live_embedding_model_id": "text-embedding-3-large",
            "live_embedding_provider_api_key": "eval-secret",
        },
        expected_payload={
            "provider_id": "embeddings.openai",
            "model_id": "text-embedding-3-large",
            "adapter_kind": "OPENAI_EMBEDDINGS_LIVE",
            "expected_outcome": "SUCCESS",
        },
    )

    with _apply_case_configuration(case.input_payload):
        summary, outcome, evidence_refs = _execute_fixture_case(
            fixture_id="provider_embedding_examples",
            fixture_task_id="provider.embeddings.v1",
            case=case,
        )

    assert outcome == EvaluationCaseOutcome.PASS
    assert "preserved provider identity and model metadata" in summary
    assert evidence_refs == ["service://platform/providers", "service://platform/providers/policy"]


def test_execute_fixture_case_reports_pass_for_retrieval_embedding_stub_posture() -> None:
    case = EvaluationFixtureRuntimeCase(
        case_id="retrieval_indexing_reports_stub_embedding_posture_when_disabled",
        summary="Retrieval indexing should report stub embedding posture when live embedding execution is not enabled.",
        input_payload={
            "retrieval_mode": "enabled",
            "embedding_provider_mode": "disabled",
        },
        expected_payload={
            "embedding_execution_enabled": False,
            "embedding_strategy": "provider-disabled",
        },
    )

    with _apply_case_configuration(case.input_payload):
        summary, outcome, evidence_refs = _execute_fixture_case(
            fixture_id="retrieval_embedding_examples",
            fixture_task_id="retrieval.embedding-runtime.v1",
            case=case,
        )

    assert outcome == EvaluationCaseOutcome.PASS
    assert "matched the expected bounded indexing posture" in summary
    assert evidence_refs == [
        "service://platform/retrieval/execution-status",
        "service://platform/retrieval/activation-readiness",
    ]


def test_execute_fixture_case_reports_pass_for_retrieval_embedding_live_posture() -> None:
    case = EvaluationFixtureRuntimeCase(
        case_id="retrieval_indexing_reports_live_embedding_posture_when_enabled",
        summary="Retrieval indexing should report live embedding posture when bounded live embedding execution is configured.",
        input_payload={
            "retrieval_mode": "enabled",
            "embedding_provider_mode": "enabled",
            "live_embedding_provider_id": "embeddings.openai",
            "live_embedding_model_id": "text-embedding-3-large",
            "live_embedding_provider_api_key": "eval-secret",
        },
        expected_payload={
            "embedding_execution_enabled": True,
            "embedding_provider_id": "embeddings.openai",
            "embedding_strategy": "provider-live-openai",
        },
    )

    with _apply_case_configuration(case.input_payload):
        summary, outcome, evidence_refs = _execute_fixture_case(
            fixture_id="retrieval_embedding_examples",
            fixture_task_id="retrieval.embedding-runtime.v1",
            case=case,
        )

    assert outcome == EvaluationCaseOutcome.PASS
    assert "matched the expected bounded indexing posture" in summary
    assert evidence_refs == [
        "service://platform/retrieval/execution-status",
        "service://platform/retrieval/activation-readiness",
    ]


def test_execute_fixture_case_reports_pass_for_live_retrieval_search_case() -> None:
    case = EvaluationFixtureRuntimeCase(
        case_id="retrieval_live_search_case",
        summary="Live retrieval should preserve citations.",
        input_payload={
            "task_id": "knowledge_search.v1",
            "query": "shared ai platform service",
            "retrieval_mode": "enabled",
            "index_sources": ["lotus-platform-rfcs"],
            "source_filters": ["lotus-platform-rfcs"],
        },
        expected_payload={
            "execution_stage": "LIVE_SEARCH",
            "provider_mode": "live_search",
            "catalog_only": False,
            "must_preserve_citations": True,
        },
    )
    with _apply_case_configuration(case.input_payload):
        summary, outcome, evidence_refs = _execute_fixture_case(
            fixture_id="retrieval_citation_examples",
            fixture_task_id="knowledge_search.v1",
            case=case,
        )

    assert outcome == EvaluationCaseOutcome.PASS
    assert "matched expected execution stage" in summary
    assert evidence_refs == [
        "service://ai/tasks/execute",
        "service://platform/retrieval/execution-status",
    ]


def test_execute_fixture_case_reports_pass_for_prompt_promotion_case() -> None:
    case = EvaluationFixtureRuntimeCase(
        case_id="prompt_promotion_updates_runtime_selection_trace",
        summary="Prompt promotion should update runtime selection trace.",
        input_payload={
            "task_id": "explain.v1",
            "caller_app": "lotus-ai",
            "promote_request": {
                "task_id": "explain.v1",
                "candidate_prompt_version": "foundation.explain.v2",
                "requested_by": "prompt-eval@lotus.test",
                "approved_by": "prompt-approver@lotus.test",
                "reason": "Evaluate prompt promotion runtime trace",
            },
            "status": "PENDING_REVIEW",
            "approval_stage": "committee_review",
        },
        expected_payload={
            "prompt_version": "foundation.explain.v2",
            "previous_active_prompt_version": "foundation.explain.v1",
            "latest_action_type": "PROMOTE_CANDIDATE",
        },
    )

    with _apply_case_configuration(case.input_payload):
        summary, outcome, evidence_refs = _execute_fixture_case(
            fixture_id="prompt_promotion_examples",
            fixture_task_id="explain.v1",
            case=case,
        )

    assert outcome == EvaluationCaseOutcome.PASS
    assert "Prompt promotion preserved" in summary
    assert evidence_refs == [
        "service://platform/prompts/control-actions",
        "service://ai/tasks/execute",
    ]


def test_execute_fixture_case_reports_pass_for_prompt_rollback_case() -> None:
    case = EvaluationFixtureRuntimeCase(
        case_id="prompt_rollback_restores_previous_active_selection",
        summary="Prompt rollback should restore previous active prompt.",
        input_payload={
            "task_id": "explain.v1",
            "caller_app": "lotus-ai",
            "promote_request": {
                "task_id": "explain.v1",
                "candidate_prompt_version": "foundation.explain.v2",
                "requested_by": "prompt-eval@lotus.test",
                "approved_by": "prompt-approver@lotus.test",
                "reason": "Stage rollback evaluation by first promoting the candidate",
            },
            "rollback_request": {
                "task_id": "explain.v1",
                "requested_by": "prompt-eval@lotus.test",
                "approved_by": "prompt-approver@lotus.test",
                "reason": "Evaluate prompt rollback runtime trace",
            },
            "status": "BLOCKED",
            "violations": 1,
            "policy_name": "exposure_guard",
        },
        expected_payload={
            "prompt_version": "foundation.explain.v1",
            "candidate_prompt_version": "foundation.explain.v2",
            "latest_action_type": "ROLLBACK_TO_PREVIOUS_ACTIVE",
        },
    )

    with _apply_case_configuration(case.input_payload):
        summary, outcome, evidence_refs = _execute_fixture_case(
            fixture_id="prompt_rollback_examples",
            fixture_task_id="explain.v1",
            case=case,
        )

    assert outcome == EvaluationCaseOutcome.PASS
    assert "Prompt rollback restored" in summary
    assert evidence_refs == [
        "service://platform/prompts/control-actions",
        "service://ai/tasks/execute",
    ]


def test_execute_fixture_case_reports_pass_for_lotus_performance_first_use_case() -> None:
    case = EvaluationFixtureRuntimeCase(
        case_id="lotus_performance_structured_commentary_authorized",
        summary="Lotus-performance commentary should remain bounded and authorized.",
        input_payload={
            "task_id": "explain.v1",
            "caller_app": "lotus-performance",
            "tenant_id": "tenant-sg-001",
            "analysis_scope": "quarterly_attribution_change",
            "period_window": {"current_period": "2026-Q1", "comparison_period": "2025-Q4"},
            "metric_deltas": [{"metric_id": "portfolio_return_bps", "delta_bps": 124}],
            "material_findings": ["Sector allocation drove the positive change."],
        },
        expected_payload={
            "output_label": "EXPLANATION_ONLY",
            "authorization_outcome": "ALLOWED",
            "caller_app": "lotus-performance",
            "task_id": "explain.v1",
            "safety_disposition": "DOCUMENTED_ONLY",
            "caller_visible_in_payload": True,
            "stubbed": True,
        },
    )

    with _apply_case_configuration(case.input_payload):
        summary, outcome, evidence_refs = _execute_fixture_case(
            fixture_id="lotus_performance_first_use_case_examples",
            fixture_task_id="explain.v1",
            case=case,
        )

    assert outcome == EvaluationCaseOutcome.PASS
    assert "Lotus-performance analytics commentary preserved" in summary
    assert evidence_refs == [
        "service://platform/use-cases/first-production-use-case/readiness",
        "service://ai/tasks/execute",
    ]


def test_execute_fixture_case_reports_unknown_runtime_semantics_for_unmapped_fixture() -> None:
    summary, outcome, evidence_refs = _execute_fixture_case(
        fixture_id="unknown_fixture_family",
        fixture_task_id="unknown_fixture_family",
        case=EvaluationFixtureRuntimeCase(
            case_id="unknown_fixture_case",
            summary="Unknown fixture family.",
            input_payload={},
            expected_payload={},
        ),
    )

    assert outcome == EvaluationCaseOutcome.FAIL
    assert "does not yet have runtime-backed execution semantics" in summary
    assert evidence_refs == ["fixture://unknown_fixture_family"]


def test_apply_case_configuration_supports_sqlalchemy_budget_and_degradation_paths(
    tmp_path: Path,
) -> None:
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-eval-runtime-config.db'}"
    upgrade_database_to_head(settings.database_url)

    with _apply_case_configuration(
        {
            "provider_operations_store_mode": "sqlalchemy",
            "hard_budget_usd": 5.0,
            "tracked_spend_usd": 1.25,
            "degraded_failure_count_threshold": 1,
        }
    ):
        assert settings.provider_operations_store_mode == "sqlalchemy"
        assert settings.live_text_budget_enforced is True
        assert settings.live_text_degradation_enforced is True

    reset_provider_operations_store_cache()


def test_apply_case_configuration_supports_sqlalchemy_circuit_open_path(tmp_path: Path) -> None:
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-eval-runtime-circuit.db'}"
    upgrade_database_to_head(settings.database_url)

    with _apply_case_configuration(
        {
            "provider_operations_store_mode": "sqlalchemy",
            "circuit_open_seconds": 30,
        }
    ):
        assert settings.provider_operations_store_mode == "sqlalchemy"
        assert settings.live_text_circuit_open_seconds == 30

    reset_provider_operations_store_cache()


def test_execute_fixture_case_reports_pass_for_runtime_safety_redaction_case() -> None:
    case = EvaluationFixtureRuntimeCase(
        case_id="runtime_safety_redacts_explanation_output",
        summary="Runtime safety should redact explanation output.",
        input_payload={
            "task_id": "explain.v1",
            "safety_mode": "runtime_enforced",
        },
        expected_payload={
            "task_status": "COMPLETED",
            "disposition": "ENFORCED_REDACTED",
            "runtime_redaction_active": True,
            "caller_app_redacted": True,
        },
    )

    with _apply_case_configuration(case.input_payload):
        summary, outcome, evidence_refs = _execute_fixture_case(
            fixture_id="safety_runtime_examples",
            fixture_task_id="safety.runtime.v1",
            case=case,
        )

    assert outcome == EvaluationCaseOutcome.PASS
    assert "expected runtime safety outcome" in summary
    assert evidence_refs == [
        "service://ai/tasks/execute",
        "service://platform/safety/runtime-status",
    ]


def test_execute_fixture_case_reports_pass_for_blocked_runtime_safety_case() -> None:
    case = EvaluationFixtureRuntimeCase(
        case_id="runtime_safety_blocks_raw_context_echo",
        summary="Runtime safety should block raw context echo.",
        input_payload={
            "safety_mode": "runtime_enforced",
            "output_label": "EXPLANATION_ONLY",
            "provider_message": "Unsafe raw payload.",
            "provider_structured_output": {"raw_context": {"account_number": "12345"}},
        },
        expected_payload={
            "disposition": "BLOCKED",
            "runtime_redaction_active": True,
        },
    )

    with _apply_case_configuration(case.input_payload):
        summary, outcome, evidence_refs = _execute_fixture_case(
            fixture_id="safety_runtime_examples",
            fixture_task_id="safety.runtime.v1",
            case=case,
        )

    assert outcome == EvaluationCaseOutcome.PASS
    assert "blocked or degraded runtime behavior" in summary
    assert evidence_refs == [
        "service://platform/safety/runtime-status",
        "service://ai/tasks/execute",
    ]


def test_execute_fixture_case_reports_failure_for_retrieval_task_execution_error() -> None:
    case = EvaluationFixtureRuntimeCase(
        case_id="retrieval_live_search_failure_case",
        summary="Live retrieval should fail when retrieval mode is disabled.",
        input_payload={
            "task_id": "missing.v1",
            "query": "shared ai platform service",
            "retrieval_mode": "disabled",
        },
        expected_payload={},
    )
    with _apply_case_configuration(case.input_payload):
        summary, outcome, evidence_refs = _execute_fixture_case(
            fixture_id="retrieval_citation_examples",
            fixture_task_id="knowledge_search.v1",
            case=case,
        )

    assert outcome == EvaluationCaseOutcome.FAIL
    assert "failed unexpectedly" in summary
    assert evidence_refs == ["service://ai/tasks/execute"]


def test_execute_fixture_case_reports_failure_for_prompt_promotion_execution_error() -> None:
    case = EvaluationFixtureRuntimeCase(
        case_id="prompt_promotion_execution_failure",
        summary="Prompt promotion eval should fail if runtime task execution fails.",
        input_payload={
            "task_id": "missing.v1",
            "promote_request": {
                "task_id": "explain.v1",
                "candidate_prompt_version": "foundation.explain.v2",
                "requested_by": "prompt-eval@lotus.test",
                "approved_by": "prompt-approver@lotus.test",
                "reason": "Evaluate prompt promotion runtime trace",
            },
        },
        expected_payload={},
    )
    with _apply_case_configuration(case.input_payload):
        summary, outcome, evidence_refs = _execute_fixture_case(
            fixture_id="prompt_promotion_examples",
            fixture_task_id="explain.v1",
            case=case,
        )

    assert outcome == EvaluationCaseOutcome.FAIL
    assert "Prompt promotion evaluation failed unexpectedly" in summary
    assert evidence_refs == [
        "service://platform/prompts/control-actions",
        "service://ai/tasks/execute",
    ]


def test_execute_fixture_case_reports_failure_for_prompt_rollback_execution_error() -> None:
    case = EvaluationFixtureRuntimeCase(
        case_id="prompt_rollback_execution_failure",
        summary="Prompt rollback eval should fail if runtime task execution fails.",
        input_payload={
            "task_id": "missing.v1",
            "promote_request": {
                "task_id": "explain.v1",
                "candidate_prompt_version": "foundation.explain.v2",
                "requested_by": "prompt-eval@lotus.test",
                "approved_by": "prompt-approver@lotus.test",
                "reason": "Promote before rollback evaluation",
            },
            "rollback_request": {
                "task_id": "explain.v1",
                "requested_by": "prompt-eval@lotus.test",
                "approved_by": "prompt-approver@lotus.test",
                "reason": "Evaluate prompt rollback runtime trace",
            },
        },
        expected_payload={},
    )
    with _apply_case_configuration(case.input_payload):
        summary, outcome, evidence_refs = _execute_fixture_case(
            fixture_id="prompt_rollback_examples",
            fixture_task_id="explain.v1",
            case=case,
        )

    assert outcome == EvaluationCaseOutcome.FAIL
    assert "Prompt rollback evaluation failed unexpectedly" in summary
    assert evidence_refs == [
        "service://platform/prompts/control-actions",
        "service://ai/tasks/execute",
    ]


def test_execute_fixture_case_reports_failure_for_runtime_safety_task_execution_error() -> None:
    case = EvaluationFixtureRuntimeCase(
        case_id="runtime_safety_redacts_explanation_output",
        summary="Safety eval should fail when task execution raises.",
        input_payload={
            "task_id": "missing.v1",
            "safety_mode": "runtime_enforced",
        },
        expected_payload={},
    )
    with _apply_case_configuration(case.input_payload):
        summary, outcome, evidence_refs = _execute_fixture_case(
            fixture_id="safety_runtime_examples",
            fixture_task_id="safety.runtime.v1",
            case=case,
        )

    assert outcome == EvaluationCaseOutcome.FAIL
    assert "Safety runtime task execution failed unexpectedly" in summary
    assert evidence_refs == ["service://ai/tasks/execute"]


def test_apply_prompt_transition_for_evaluation_rejects_missing_rollout_state() -> None:
    try:
        _apply_prompt_transition_for_evaluation(
            task_id="missing.v1",
            candidate_prompt_version="foundation.explain.v2",
            requested_by="prompt-eval@lotus.test",
            approved_by="prompt-approver@lotus.test",
            reason="Missing rollout state",
        )
    except HTTPException as exc:
        assert exc.status_code == 404
        assert "rollout state" in str(exc.detail)
    else:
        raise AssertionError("Expected missing rollout state to fail")


def test_apply_prompt_transition_for_evaluation_rejects_missing_and_invalid_candidates() -> None:
    try:
        _apply_prompt_transition_for_evaluation(
            task_id="explain.v1",
            candidate_prompt_version="missing.version",
            requested_by="prompt-eval@lotus.test",
            approved_by="prompt-approver@lotus.test",
            reason="Missing candidate",
        )
    except HTTPException as exc:
        assert exc.status_code == 404
        assert "Candidate prompt version" in str(exc.detail)
    else:
        raise AssertionError("Expected missing candidate prompt to fail")

    try:
        _apply_prompt_transition_for_evaluation(
            task_id="explain.v1",
            candidate_prompt_version="foundation.explain.v1",
            requested_by="prompt-eval@lotus.test",
            approved_by="prompt-approver@lotus.test",
            reason="Non-candidate prompt version",
        )
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "not a governed candidate" in str(exc.detail)
    else:
        raise AssertionError("Expected non-candidate prompt to fail")


def test_apply_prompt_transition_for_evaluation_rejects_missing_active_prompt(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'eval-prompt-missing-active.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(prompt_store_mode="sqlalchemy", database_url=database_url):
        repository = get_prompt_repository()
        rollout_state = repository.get_prompt_rollout_state("explain.v1")
        candidate_prompt = repository.get_prompt_version("explain.v1", "foundation.explain.v2")
        assert rollout_state is not None
        assert candidate_prompt is not None
        repository.save_prompt_rollout_transition(
            rollout_state=PromptRolloutStateRecord(
                task_id=rollout_state.task_id,
                active_prompt_version="missing.version",
                candidate_prompt_version=rollout_state.candidate_prompt_version,
                previous_active_prompt_version=rollout_state.previous_active_prompt_version,
                rollout_mode=rollout_state.rollout_mode,
                runtime_mutation_enabled=rollout_state.runtime_mutation_enabled,
            ),
            updated_prompts=[candidate_prompt],
            event=PromptRolloutEventRecord(
                event_id="prompt_evt_eval_missing_active",
                task_id="explain.v1",
                action_type=PromptControlActionType.PROMOTE_CANDIDATE,
                requested_by="prompt-eval@lotus.test",
                approved_by="prompt-approver@lotus.test",
                reason="Exercise missing active prompt branch",
                prior_active_prompt_version="foundation.explain.v1",
                resulting_active_prompt_version="missing.version",
                prior_candidate_prompt_version=rollout_state.candidate_prompt_version,
                resulting_candidate_prompt_version=rollout_state.candidate_prompt_version,
                authorization=_authorization(),
                recorded_at="2026-03-24T09:00:00Z",
            ),
        )

        try:
            _apply_prompt_transition_for_evaluation(
                task_id="explain.v1",
                candidate_prompt_version="foundation.explain.v2",
                requested_by="prompt-eval@lotus.test",
                approved_by="prompt-approver@lotus.test",
                reason="Missing active prompt",
            )
        except HTTPException as exc:
            assert exc.status_code == 409
            assert "references missing active prompt" in str(exc.detail)
        else:
            raise AssertionError("Expected missing active prompt to fail")


def test_apply_prompt_rollback_for_evaluation_rejects_missing_state_and_versions(
    tmp_path: Path,
) -> None:
    try:
        _apply_prompt_rollback_for_evaluation(
            task_id="missing.v1",
            requested_by="prompt-eval@lotus.test",
            approved_by="prompt-approver@lotus.test",
            reason="Missing state",
        )
    except HTTPException as exc:
        assert exc.status_code == 404
        assert "rollout state" in str(exc.detail)
    else:
        raise AssertionError("Expected missing rollback state to fail")

    database_url = f"sqlite:///{tmp_path / 'eval-prompt-rollback.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(
        prompt_store_mode="sqlalchemy",
        evaluation_runtime_store_mode="sqlalchemy",
        database_url=database_url,
    ):
        get_evaluation_runtime_store().save_run(
            EvaluationRunRecord(
                run_id="runtime_prompt_eval_promotion",
                fixture_id="prompt_promotion_examples",
                manifest_version="foundation.v1",
                lifecycle_status="COMPLETED",
                triggered_by="operator-a",
                submitted_at="2026-03-24T09:00:00Z",
                async_job_id="async_prompt_eval_promotion",
                latest_message="Prompt promotion approval fixture passed.",
                verdict="PASS",
                case_count=1,
            )
        )
        get_evaluation_runtime_store().save_run(
            EvaluationRunRecord(
                run_id="runtime_prompt_eval_rollback",
                fixture_id="prompt_rollback_examples",
                manifest_version="foundation.v1",
                lifecycle_status="COMPLETED",
                triggered_by="operator-a",
                submitted_at="2026-03-24T09:00:00Z",
                async_job_id="async_prompt_eval_rollback",
                latest_message="Prompt rollback approval fixture passed.",
                verdict="PASS",
                case_count=1,
            )
        )
        apply_prompt_control_action(
            PromptControlActionRequest(
                task_id="explain.v1",
                action_type=PromptControlActionType.PROMOTE_CANDIDATE,
                caller_app="lotus-platform",
                candidate_prompt_version="foundation.explain.v2",
                requested_by="alice@lotus.test",
                approved_by="bob@lotus.test",
                reason="Promote before rollback error coverage",
            )
        )

        repository = get_prompt_repository()
        rollout_state = repository.get_prompt_rollout_state("explain.v1")
        active_prompt = repository.get_prompt_version("explain.v1", "foundation.explain.v2")
        assert rollout_state is not None
        assert active_prompt is not None
        repository.save_prompt_rollout_transition(
            rollout_state=PromptRolloutStateRecord(
                task_id=rollout_state.task_id,
                active_prompt_version=rollout_state.active_prompt_version,
                candidate_prompt_version=rollout_state.candidate_prompt_version,
                previous_active_prompt_version=None,
                rollout_mode=rollout_state.rollout_mode,
                runtime_mutation_enabled=rollout_state.runtime_mutation_enabled,
            ),
            updated_prompts=[active_prompt],
            event=PromptRolloutEventRecord(
                event_id="prompt_evt_eval_no_previous",
                task_id="explain.v1",
                action_type=PromptControlActionType.PROMOTE_CANDIDATE,
                requested_by="alice@lotus.test",
                approved_by="bob@lotus.test",
                reason="Exercise no previous active branch",
                prior_active_prompt_version="foundation.explain.v2",
                resulting_active_prompt_version="foundation.explain.v2",
                prior_candidate_prompt_version=None,
                resulting_candidate_prompt_version=None,
                authorization=_authorization(),
                recorded_at="2026-03-24T09:10:00Z",
            ),
        )

        try:
            _apply_prompt_rollback_for_evaluation(
                task_id="explain.v1",
                requested_by="prompt-eval@lotus.test",
                approved_by="prompt-approver@lotus.test",
                reason="No previous active prompt",
            )
        except HTTPException as exc:
            assert exc.status_code == 409
            assert "no prior active prompt" in str(exc.detail)
        else:
            raise AssertionError("Expected missing previous active prompt to fail")


def test_apply_prompt_rollback_for_evaluation_rejects_missing_prompt_versions(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'eval-prompt-rollback-missing-versions.db'}"
    upgrade_database_to_head(database_url)

    with override_runtime_settings(prompt_store_mode="sqlalchemy", database_url=database_url):
        repository = get_prompt_repository()
        rollout_state = repository.get_prompt_rollout_state("explain.v1")
        candidate_prompt = repository.get_prompt_version("explain.v1", "foundation.explain.v2")
        assert rollout_state is not None
        assert candidate_prompt is not None
        repository.save_prompt_rollout_transition(
            rollout_state=PromptRolloutStateRecord(
                task_id=rollout_state.task_id,
                active_prompt_version="foundation.explain.v2",
                candidate_prompt_version=rollout_state.candidate_prompt_version,
                previous_active_prompt_version="missing.version",
                rollout_mode=rollout_state.rollout_mode,
                runtime_mutation_enabled=rollout_state.runtime_mutation_enabled,
            ),
            updated_prompts=[candidate_prompt],
            event=PromptRolloutEventRecord(
                event_id="prompt_evt_eval_missing_versions",
                task_id="explain.v1",
                action_type=PromptControlActionType.PROMOTE_CANDIDATE,
                requested_by="alice@lotus.test",
                approved_by="bob@lotus.test",
                reason="Exercise missing rollback versions branch",
                prior_active_prompt_version="foundation.explain.v1",
                resulting_active_prompt_version="foundation.explain.v2",
                prior_candidate_prompt_version=None,
                resulting_candidate_prompt_version=None,
                authorization=_authorization(),
                recorded_at="2026-03-24T09:15:00Z",
            ),
        )

        try:
            _apply_prompt_rollback_for_evaluation(
                task_id="explain.v1",
                requested_by="prompt-eval@lotus.test",
                approved_by="prompt-approver@lotus.test",
                reason="Missing rollback prompt versions",
            )
        except HTTPException as exc:
            assert exc.status_code == 409
            assert "references missing prompt versions" in str(exc.detail)
        else:
            raise AssertionError("Expected missing rollback prompt versions to fail")
