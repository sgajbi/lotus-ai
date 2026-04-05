from __future__ import annotations

from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from typing import Any, Iterator, cast

from fastapi import HTTPException

from app.config import settings
from app.contracts.access_control import (
    AuthorizationCapabilityType,
    AuthorizationDecision,
    AuthorizationOutcome,
    TenantPolicyMode,
)
from app.contracts.evals import EvaluationCaseOutcome, EvaluationRunVerdict
from app.contracts.prompts import (
    PromptControlActionType,
    PromptLifecycleStatus,
    PromptRolloutSelectionMode,
)
from app.contracts.providers import ProviderFailureCategory, ProviderQuotaScope
from app.contracts.safety import SafetyExecutionOutcome
from app.contracts.tasks import (
    CallerMetadata,
    OutputLabel,
    TaskContextEnvelope,
    TaskExecutionResponse,
    TaskExecutionRequest,
    TaskInputMode,
)
from app.evals.fixture_manifest import (
    EvaluationFixtureRuntimeCase,
    load_evaluation_fixture_runtime_cases,
)
from app.repositories.evaluation_runtime_repository import (
    EvaluationCaseResultRecord,
    EvaluationRunAttemptRecord,
    EvaluationRunRecord,
)
from app.services.eval_run_submission_service import RUNTIME_BACKED_EVALUATION_FIXTURE_IDS
from app.services.artifact_payloads import persist_json_artifact
from app.services.embedding_live_execution_state import build_embedding_live_execution_state
from app.services.evaluation_runtime_store import get_evaluation_runtime_store
from app.services.prompt_rollout_models import PromptRolloutEventRecord, PromptRolloutStateRecord
from app.services.prompt_store import get_prompt_repository
from app.services.prompt_store import reset_prompt_store_cache
from app.services.provider_budget_policy import build_provider_budget_policy
from app.services.provider_catalog import build_provider_catalog
from app.services.provider_configuration_status import build_embedding_configuration_status
from app.services.provider_degradation_state import (
    record_provider_failure,
    reset_provider_degradation_state,
)
from app.services.provider_operations_status import build_provider_operations_status
from app.services.provider_policy import build_provider_policy
from app.services.provider_operations_store import (
    get_provider_operations_store,
    reset_provider_operations_store_cache,
)
from app.services.provider_quota_policy import reset_provider_quota_counters
from app.services.retrieval_embedding_runtime import build_retrieval_embedding_runtime
from app.services.retrieval_execution_status import build_retrieval_execution_status
from app.services.retrieval_store import get_retrieval_repository, reset_retrieval_repository
from app.services.safety_enforcement import (
    apply_safety_enforcement,
    resolve_safety_policy_for_output,
)
from app.services.safety_policy import build_safety_policy
from app.services.safety_status import build_safety_runtime_status
from app.services.task_executor import execute_task


@dataclass(frozen=True)
class EvaluationExecutionResult:
    run_id: str
    attempt_id: str
    verdict: EvaluationRunVerdict
    case_result_count: int


def execute_runtime_backed_evaluation_run(
    *, run_id: str, worker_id: str
) -> EvaluationExecutionResult:
    store = get_evaluation_runtime_store()
    run = store.get_run(run_id=run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Evaluation run '{run_id}' was not found.")

    attempt = _get_active_attempt(run_id=run_id)
    if attempt is None:
        raise HTTPException(
            status_code=409,
            detail=f"Evaluation run '{run_id}' has no queued runtime attempt to execute.",
        )

    task_id, cases = load_evaluation_fixture_runtime_cases(fixture_id=run.fixture_id)
    if run.fixture_id not in RUNTIME_BACKED_EVALUATION_FIXTURE_IDS or task_id is None:
        raise HTTPException(
            status_code=409,
            detail=f"Evaluation fixture family '{run.fixture_id}' is not executable in runtime-backed mode.",
        )

    started_at = _utcnow_iso()
    store.save_attempt(
        EvaluationRunAttemptRecord(
            attempt_id=attempt.attempt_id,
            run_id=attempt.run_id,
            attempt_number=attempt.attempt_number,
            lifecycle_status="RUNNING",
            started_at=started_at,
            completed_at=None,
            worker_id=worker_id,
            latest_message=f"Runtime-backed evaluation attempt started by worker '{worker_id}'.",
            verdict=None,
            failure_reason=None,
        )
    )
    store.save_run(
        EvaluationRunRecord(
            run_id=run.run_id,
            fixture_id=run.fixture_id,
            manifest_version=run.manifest_version,
            lifecycle_status="RUNNING",
            triggered_by=run.triggered_by,
            submitted_at=run.submitted_at,
            async_job_id=run.async_job_id,
            latest_message=f"Evaluation run is executing under worker '{worker_id}'.",
            verdict=None,
            case_count=run.case_count,
        )
    )

    persisted_results = [
        _evaluate_case(
            run=run,
            attempt_id=attempt.attempt_id,
            fixture_task_id=task_id,
            case=case,
        )
        for case in cases
    ]
    for result in persisted_results:
        store.save_case_result(result)

    verdict = (
        EvaluationRunVerdict.PASS
        if all(result.outcome == EvaluationCaseOutcome.PASS.value for result in persisted_results)
        else EvaluationRunVerdict.FAIL
    )
    completed_at = _utcnow_iso()
    store.save_attempt(
        EvaluationRunAttemptRecord(
            attempt_id=attempt.attempt_id,
            run_id=attempt.run_id,
            attempt_number=attempt.attempt_number,
            lifecycle_status="COMPLETED",
            started_at=started_at,
            completed_at=completed_at,
            worker_id=worker_id,
            latest_message=f"Runtime-backed evaluation attempt completed with verdict '{verdict.value}'.",
            verdict=verdict.value,
            failure_reason=None,
        )
    )
    store.save_run(
        EvaluationRunRecord(
            run_id=run.run_id,
            fixture_id=run.fixture_id,
            manifest_version=run.manifest_version,
            lifecycle_status="COMPLETED" if verdict == EvaluationRunVerdict.PASS else "FAILED",
            triggered_by=run.triggered_by,
            submitted_at=run.submitted_at,
            async_job_id=run.async_job_id,
            latest_message=f"Runtime-backed evaluation run completed with verdict '{verdict.value}'.",
            verdict=verdict.value,
            case_count=run.case_count,
        )
    )
    return EvaluationExecutionResult(
        run_id=run.run_id,
        attempt_id=attempt.attempt_id,
        verdict=verdict,
        case_result_count=len(persisted_results),
    )


def _get_active_attempt(*, run_id: str) -> EvaluationRunAttemptRecord | None:
    attempts = get_evaluation_runtime_store().list_attempts(run_id=run_id)
    for attempt in reversed(attempts):
        if attempt.lifecycle_status in {"QUEUED", "SUBMITTED", "CLAIMED"}:
            return attempt
    return None


def _evaluate_case(
    *,
    run: EvaluationRunRecord,
    attempt_id: str,
    fixture_task_id: str,
    case: EvaluationFixtureRuntimeCase,
) -> EvaluationCaseResultRecord:
    with _apply_case_configuration(case.input_payload):
        summary, outcome, evidence_refs = _execute_fixture_case(
            fixture_id=run.fixture_id,
            fixture_task_id=fixture_task_id,
            case=case,
        )
    case_result_id = f"{attempt_id}_{case.case_id}"
    artifact = persist_json_artifact(
        domain="evaluation",
        artifact_type="case_result_bundle",
        source_object_kind="evaluation_case_result",
        source_object_id=case_result_id,
        created_at=_utcnow_iso(),
        created_by="worker",
        payload_json=json.dumps(
            {
                "run_id": run.run_id,
                "attempt_id": attempt_id,
                "case_id": case.case_id,
                "fixture_id": run.fixture_id,
                "outcome": outcome.value,
                "summary": summary,
                "evidence_refs": evidence_refs,
            },
            sort_keys=True,
        ).encode("utf-8"),
    )
    return EvaluationCaseResultRecord(
        case_result_id=case_result_id,
        run_id=run.run_id,
        attempt_id=attempt_id,
        case_id=case.case_id,
        fixture_id=run.fixture_id,
        outcome=outcome.value,
        summary=summary,
        evidence_refs=evidence_refs,
        artifact_ids=[artifact.artifact_id],
        recorded_at=_utcnow_iso(),
    )


def _execute_fixture_case(
    *,
    fixture_id: str,
    fixture_task_id: str,
    case: EvaluationFixtureRuntimeCase,
) -> tuple[str, EvaluationCaseOutcome, list[str]]:
    if fixture_id == "retrieval_citation_examples":
        task_id = str(case.input_payload.get("task_id", fixture_task_id))
        response, failure_category = _execute_task_case(task_id=task_id, case=case)
        if response is None:
            return (
                f"Retrieval task execution failed unexpectedly with '{failure_category}'.",
                EvaluationCaseOutcome.FAIL,
                ["service://ai/tasks/execute"],
            )
        retrieval_status = build_retrieval_execution_status()
        structured_output = response.result.structured_output
        checks = [
            structured_output.get("execution_stage")
            == case.expected_payload.get("execution_stage"),
            response.audit.provider_mode == case.expected_payload.get("provider_mode"),
        ]
        if case.expected_payload.get("must_preserve_citations"):
            checks.append(int(structured_output.get("citation_count", 0)) >= 1)
            checks.append(len(structured_output.get("citations", [])) >= 1)
        if case.expected_payload.get("answer_mode") is not None:
            checks.append(
                structured_output.get("answer_mode") == case.expected_payload["answer_mode"]
            )
        if case.expected_payload.get("catalog_only") is not None:
            checks.append(
                structured_output.get("catalog_only") == case.expected_payload["catalog_only"]
            )
        checks.append(retrieval_status.live_search_enabled is True)
        outcome = EvaluationCaseOutcome.PASS if all(checks) else EvaluationCaseOutcome.FAIL
        return (
            (
                "Live retrieval task execution matched expected execution stage, citation posture, and answer behavior."
                if outcome == EvaluationCaseOutcome.PASS
                else "Live retrieval task execution did not match expected execution stage, citation posture, or answer behavior."
            ),
            outcome,
            ["service://ai/tasks/execute", "service://platform/retrieval/execution-status"],
        )

    if fixture_id == "retrieval_embedding_examples":
        embedding_runtime = build_retrieval_embedding_runtime()
        retrieval_status = build_retrieval_execution_status()
        checks = [
            embedding_runtime.embedding_execution_enabled
            == case.expected_payload["embedding_execution_enabled"],
            embedding_runtime.embedding_strategy == case.expected_payload["embedding_strategy"],
            retrieval_status.embedding_execution_enabled
            == case.expected_payload["embedding_execution_enabled"],
        ]
        if case.expected_payload.get("embedding_provider_id") is not None:
            checks.append(
                embedding_runtime.embedding_provider_id
                == case.expected_payload["embedding_provider_id"]
            )
            checks.append(
                retrieval_status.embedding_provider_id
                == case.expected_payload["embedding_provider_id"]
            )
        outcome = EvaluationCaseOutcome.PASS if all(checks) else EvaluationCaseOutcome.FAIL
        return (
            (
                "Retrieval embedding runtime matched the expected bounded indexing posture."
                if outcome == EvaluationCaseOutcome.PASS
                else "Retrieval embedding runtime did not match the expected bounded indexing posture."
            ),
            outcome,
            [
                "service://platform/retrieval/execution-status",
                "service://platform/retrieval/activation-readiness",
            ],
        )

    if fixture_id == "prompt_promotion_examples":
        promote_request = case.input_payload["promote_request"]
        _apply_prompt_transition_for_evaluation(
            task_id=str(promote_request["task_id"]),
            candidate_prompt_version=str(promote_request["candidate_prompt_version"]),
            requested_by=str(promote_request["requested_by"]),
            approved_by=str(promote_request["approved_by"]),
            reason=str(promote_request["reason"]),
        )
        response, failure_category = _execute_task_case(
            task_id=str(case.input_payload["task_id"]),
            case=case,
        )
        if response is None:
            return (
                f"Prompt promotion evaluation failed unexpectedly with '{failure_category}'.",
                EvaluationCaseOutcome.FAIL,
                ["service://platform/prompts/control-actions", "service://ai/tasks/execute"],
            )
        checks = [
            response.audit.prompt_version == case.expected_payload["prompt_version"],
            response.audit.prompt_selection.prompt_version
            == case.expected_payload["prompt_version"],
            response.audit.prompt_selection.previous_active_prompt_version
            == case.expected_payload["previous_active_prompt_version"],
            response.audit.prompt_selection.latest_control_event is not None,
            response.audit.prompt_selection.latest_control_event is not None
            and response.audit.prompt_selection.latest_control_event.action_type.value
            == case.expected_payload["latest_action_type"],
        ]
        outcome = EvaluationCaseOutcome.PASS if all(checks) else EvaluationCaseOutcome.FAIL
        return (
            (
                "Prompt promotion preserved the expected runtime selection lineage and audit trace."
                if outcome == EvaluationCaseOutcome.PASS
                else "Prompt promotion did not preserve the expected runtime selection lineage and audit trace."
            ),
            outcome,
            ["service://platform/prompts/control-actions", "service://ai/tasks/execute"],
        )

    if fixture_id == "prompt_rollback_examples":
        promote_request = case.input_payload["promote_request"]
        _apply_prompt_transition_for_evaluation(
            task_id=str(promote_request["task_id"]),
            candidate_prompt_version=str(promote_request["candidate_prompt_version"]),
            requested_by=str(promote_request["requested_by"]),
            approved_by=str(promote_request["approved_by"]),
            reason=str(promote_request["reason"]),
        )
        rollback_request = case.input_payload["rollback_request"]
        _apply_prompt_rollback_for_evaluation(
            task_id=str(rollback_request["task_id"]),
            requested_by=str(rollback_request["requested_by"]),
            approved_by=str(rollback_request["approved_by"]),
            reason=str(rollback_request["reason"]),
        )
        response, failure_category = _execute_task_case(
            task_id=str(case.input_payload["task_id"]),
            case=case,
        )
        if response is None:
            return (
                f"Prompt rollback evaluation failed unexpectedly with '{failure_category}'.",
                EvaluationCaseOutcome.FAIL,
                ["service://platform/prompts/control-actions", "service://ai/tasks/execute"],
            )
        checks = [
            response.audit.prompt_version == case.expected_payload["prompt_version"],
            response.audit.prompt_selection.prompt_version
            == case.expected_payload["prompt_version"],
            response.audit.prompt_selection.candidate_prompt_version
            == case.expected_payload["candidate_prompt_version"],
            response.audit.prompt_selection.previous_active_prompt_version is None,
            response.audit.prompt_selection.latest_control_event is not None,
            response.audit.prompt_selection.latest_control_event is not None
            and response.audit.prompt_selection.latest_control_event.action_type.value
            == case.expected_payload["latest_action_type"],
        ]
        outcome = EvaluationCaseOutcome.PASS if all(checks) else EvaluationCaseOutcome.FAIL
        return (
            (
                "Prompt rollback restored the expected runtime selection lineage and candidate posture."
                if outcome == EvaluationCaseOutcome.PASS
                else "Prompt rollback did not restore the expected runtime selection lineage and candidate posture."
            ),
            outcome,
            ["service://platform/prompts/control-actions", "service://ai/tasks/execute"],
        )

    if fixture_id == "capability_pack_analytics_commentary_examples":
        return _evaluate_capability_pack_case(
            fixture_task_id=fixture_task_id,
            pack_id="analytics_commentary.pack.v1",
            failure_label="Analytics commentary pack evaluation",
            pass_summary=(
                "Analytics commentary pack execution preserved bounded explanation-only output, "
                "caller authorization, and product-quality guardrails."
            ),
            fail_summary=(
                "Analytics commentary pack execution did not preserve the expected authorization "
                "or product-quality guardrails."
            ),
            case=case,
        )

    if fixture_id == "capability_pack_decision_explanation_examples":
        return _evaluate_capability_pack_case(
            fixture_task_id=fixture_task_id,
            pack_id="decision_explanation.pack.v1",
            failure_label="Decision explanation pack evaluation",
            pass_summary=(
                "Decision explanation pack execution preserved bounded explanation-only output, "
                "caller authorization, and deterministic explanation guardrails."
            ),
            fail_summary=(
                "Decision explanation pack execution did not preserve the expected authorization "
                "or deterministic explanation guardrails."
            ),
            case=case,
        )

    if fixture_id == "lotus_performance_first_use_case_examples":
        task_id = str(case.input_payload.get("task_id", fixture_task_id))
        response, failure_category = _execute_task_case(task_id=task_id, case=case)
        if response is None:
            return (
                f"First-use-case commentary evaluation failed unexpectedly with '{failure_category}'.",
                EvaluationCaseOutcome.FAIL,
                [
                    "service://platform/use-cases/first-production-use-case/readiness",
                    "service://ai/tasks/execute",
                ],
            )
        caller_visible_in_payload = "caller_app" in response.result.structured_output
        checks = [
            response.output_label.value == case.expected_payload["output_label"],
            response.audit.authorization.outcome.value
            == case.expected_payload["authorization_outcome"],
            response.audit.authorization.caller_app == case.expected_payload["caller_app"],
            response.audit.authorization.task_id == case.expected_payload["task_id"],
            response.audit.safety.disposition.value == case.expected_payload["safety_disposition"],
            caller_visible_in_payload == case.expected_payload["caller_visible_in_payload"],
            response.audit.stubbed is bool(case.expected_payload["stubbed"]),
        ]
        outcome = EvaluationCaseOutcome.PASS if all(checks) else EvaluationCaseOutcome.FAIL
        return (
            (
                "Lotus-performance analytics commentary preserved bounded explanation-only output, caller authorization, and safety posture."
                if outcome == EvaluationCaseOutcome.PASS
                else "Lotus-performance analytics commentary did not preserve the expected authorization or explanation-only safety posture."
            ),
            outcome,
            [
                "service://platform/use-cases/first-production-use-case/readiness",
                "service://ai/tasks/execute",
            ],
        )

    if fixture_id == "provider_policy_examples":
        policy = build_provider_policy().policies[
            0 if case.input_payload["capability"] == "TEXT_GENERATION" else 1
        ]
        selected_matches = (
            policy.selected_provider_id == case.expected_payload["selected_provider_id"]
        )
        live_flag_matches = (
            policy.live_execution_enabled == case.expected_payload["live_execution_enabled"]
        )
        outcome = (
            EvaluationCaseOutcome.PASS
            if selected_matches and live_flag_matches
            else EvaluationCaseOutcome.FAIL
        )
        return (
            (
                "Provider policy matched the expected selected provider and live-execution posture."
                if outcome == EvaluationCaseOutcome.PASS
                else "Provider policy did not match the expected selected provider or live-execution posture."
            ),
            outcome,
            ["service://platform/providers/policy"],
        )

    if fixture_id == "provider_runtime_examples":
        task_id = str(case.input_payload.get("task_id", fixture_task_id))
        response, failure_category = _execute_task_case(task_id=task_id, case=case)
        if case.expected_payload["expected_outcome"] == "SUCCESS":
            provider_resolution = (
                next(
                    (
                        descriptor
                        for descriptor in response.evidence.descriptors
                        if descriptor.evidence_type == "provider_resolution"
                    ),
                    None,
                )
                if response is not None
                else None
            )
            controls_present = (
                provider_resolution is not None
                and provider_resolution.attributes.get("timeout_ms") is not None
                and provider_resolution.attributes.get("max_output_tokens") is not None
            )
            provider_mode_matches = (
                response is not None
                and response.audit.provider_mode
                == case.expected_payload.get("provider_mode", response.audit.provider_mode)
            )
            provider_id_matches = (
                response is not None
                and response.audit.provider_id
                == case.expected_payload.get("provider_id", response.audit.provider_id)
            )
            adapter_kind_matches = response is not None and (
                response.audit.adapter_kind is not None
                and response.audit.adapter_kind.value
                == case.expected_payload.get(
                    "adapter_kind",
                    response.audit.adapter_kind.value,
                )
            )
            stubbed_matches = (
                response is not None
                and response.audit.stubbed
                == case.expected_payload.get("stubbed", response.audit.stubbed)
            )
            outcome = (
                EvaluationCaseOutcome.PASS
                if (
                    controls_present
                    and provider_mode_matches
                    and provider_id_matches
                    and adapter_kind_matches
                    and stubbed_matches
                )
                else EvaluationCaseOutcome.FAIL
            )
            return (
                (
                    "Task execution preserved bounded provider controls and explicit provider identity in runtime evidence."
                    if outcome == EvaluationCaseOutcome.PASS
                    else "Task execution did not preserve the expected bounded provider controls or provider identity."
                ),
                outcome,
                ["service://ai/tasks/execute"],
            )
        expected_failure = case.expected_payload["failure_category"]
        outcome = (
            EvaluationCaseOutcome.PASS
            if failure_category == expected_failure
            else EvaluationCaseOutcome.FAIL
        )
        return (
            (
                f"Live-provider rejection matched expected failure category '{expected_failure}'."
                if outcome == EvaluationCaseOutcome.PASS
                else f"Live-provider rejection did not match expected failure category '{expected_failure}'."
            ),
            outcome,
            ["service://ai/tasks/execute"],
        )

    if fixture_id == "provider_embedding_examples":
        if case.expected_payload["expected_outcome"] == "REJECTION":
            embedding_state = build_embedding_live_execution_state()
            configuration = build_embedding_configuration_status()
            outcome = (
                EvaluationCaseOutcome.PASS
                if (
                    embedding_state.live_execution_enabled is False
                    and configuration.configuration_valid is False
                    and case.expected_payload["failure_category"] == "INVALID_LIVE_CONFIGURATION"
                )
                else EvaluationCaseOutcome.FAIL
            )
            return (
                (
                    "Live embedding configuration rejection matched the expected invalid configuration posture."
                    if outcome == EvaluationCaseOutcome.PASS
                    else "Live embedding configuration rejection did not match the expected invalid configuration posture."
                ),
                outcome,
                ["service://platform/providers", "service://platform/providers/policy"],
            )

        embedding_state = build_embedding_live_execution_state()
        provider_catalog = build_provider_catalog()
        embedding_provider = next(
            provider
            for provider in provider_catalog.providers
            if provider.provider_id == case.expected_payload["provider_id"]
        )
        checks = [
            embedding_state.live_execution_enabled is True,
            embedding_state.configured_provider_id == case.expected_payload["provider_id"],
            embedding_state.configured_model_id == case.expected_payload["model_id"],
            embedding_provider.adapter_kind.value == case.expected_payload["adapter_kind"],
            provider_catalog.embedding_runtime_execution_enabled is True,
        ]
        outcome = EvaluationCaseOutcome.PASS if all(checks) else EvaluationCaseOutcome.FAIL
        return (
            (
                "Bounded live embedding configuration preserved provider identity and model metadata without drifting into an ungoverned path."
                if outcome == EvaluationCaseOutcome.PASS
                else "Bounded live embedding configuration did not preserve the expected provider identity and model metadata."
            ),
            outcome,
            ["service://platform/providers", "service://platform/providers/policy"],
        )

    if fixture_id == "provider_failure_mode_examples":
        task_id = str(case.input_payload.get("task_id", fixture_task_id))
        response, failure_category = _execute_task_case(task_id=task_id, case=case)
        if case.expected_payload["expected_outcome"] == "TIMEOUT_GUARDRAIL":
            controls_present = (
                response is not None
                and response.result.structured_output.get("timeout_ms") is not None
            )
            outcome = EvaluationCaseOutcome.PASS if controls_present else EvaluationCaseOutcome.FAIL
            return (
                (
                    "Provider timeout budget remained explicit in task execution evidence."
                    if outcome == EvaluationCaseOutcome.PASS
                    else "Provider timeout budget was not preserved in task execution evidence."
                ),
                outcome,
                ["service://ai/tasks/execute"],
            )
        if case.expected_payload["expected_outcome"] == "LOCAL_UPSTREAM_FAILURE":
            expected_failure = case.expected_payload["failure_category"]
            outcome = (
                EvaluationCaseOutcome.PASS
                if failure_category == expected_failure
                else EvaluationCaseOutcome.FAIL
            )
            return (
                (
                    f"Local OpenAI-compatible provider failure mapped cleanly to '{expected_failure}'."
                    if outcome == EvaluationCaseOutcome.PASS
                    else f"Local OpenAI-compatible provider failure did not map cleanly to '{expected_failure}'."
                ),
                outcome,
                [
                    "service://ai/tasks/execute",
                    "service://platform/providers/operations-status",
                ],
            )
        outcome = (
            EvaluationCaseOutcome.PASS
            if failure_category == "LIVE_EXECUTION_NOT_ENABLED"
            else EvaluationCaseOutcome.FAIL
        )
        return (
            (
                "Blocked live-provider path rejected explicitly without silent drift."
                if outcome == EvaluationCaseOutcome.PASS
                else "Blocked live-provider path did not reject explicitly as expected."
            ),
            outcome,
            ["service://ai/tasks/execute"],
        )

    if fixture_id in {"provider_operations_examples", "provider_degradation_examples"}:
        task_id = str(case.input_payload.get("task_id", fixture_task_id))
        if fixture_id == "provider_operations_examples" and case.expected_payload.get(
            "budget_state"
        ):
            budget_policy = build_provider_budget_policy()
            budget_match = budget_policy.budget_state.value == case.expected_payload["budget_state"]
            outcome = EvaluationCaseOutcome.PASS if budget_match else EvaluationCaseOutcome.FAIL
            return (
                (
                    "Provider budget posture matched the expected durable runtime evidence."
                    if outcome == EvaluationCaseOutcome.PASS
                    else "Provider budget posture did not match the expected durable runtime evidence."
                ),
                outcome,
                ["service://platform/providers/budget-policy"],
            )

        operations = build_provider_operations_status()
        expected_state = case.expected_payload.get("operations_state")
        expected_failure = case.expected_payload.get("failure_category")
        state_match = expected_state is None or operations.operations_state.value == expected_state
        failure_match = True
        if expected_failure is not None:
            _response, observed_failure = _execute_task_case(task_id=task_id, case=case)
            failure_match = observed_failure == expected_failure
        outcome = (
            EvaluationCaseOutcome.PASS
            if state_match and failure_match
            else EvaluationCaseOutcome.FAIL
        )
        summary = "Provider operations posture matched expected runtime evidence."
        if outcome == EvaluationCaseOutcome.FAIL:
            summary = "Provider operations posture did not match expected runtime evidence."
        return (summary, outcome, ["service://platform/providers/operations-status"])

    if fixture_id == "safety_policy_examples":
        if case.case_id == "explanation_task_requires_minimization":
            safety_policy = build_safety_policy()
            task_policy = next(
                item
                for item in safety_policy.task_policies
                if item.task_id == case.input_payload["task_id"]
            )
            checks = [
                task_policy.output_label == case.input_payload["output_label"],
                task_policy.redaction_posture.value == case.expected_payload["redaction_posture"],
                task_policy.response_labeling_required
                == case.expected_payload["response_labeling_required"],
                case.expected_payload["intended_use_note_contains"]
                in task_policy.intended_use_notes,
            ]
            outcome = EvaluationCaseOutcome.PASS if all(checks) else EvaluationCaseOutcome.FAIL
            return (
                (
                    "Safety policy matched the expected output-label minimization posture."
                    if outcome == EvaluationCaseOutcome.PASS
                    else "Safety policy did not match the expected output-label minimization posture."
                ),
                outcome,
                ["service://platform/safety/policy"],
            )
        runtime_status = build_safety_runtime_status()
        checks = [
            runtime_status.enforced_control_ids == case.expected_payload["enforced_control_ids"],
            runtime_status.documented_only_control_ids
            == case.expected_payload["documented_only_control_ids"],
            runtime_status.runtime_redaction_active
            == case.expected_payload["runtime_redaction_active"],
        ]
        outcome = EvaluationCaseOutcome.PASS if all(checks) else EvaluationCaseOutcome.FAIL
        return (
            (
                "Safety runtime status matched the expected enforced-versus-documented posture."
                if outcome == EvaluationCaseOutcome.PASS
                else "Safety runtime status did not match the expected enforced-versus-documented posture."
            ),
            outcome,
            ["service://platform/safety/runtime-status"],
        )

    if fixture_id == "safety_runtime_examples":
        if case.case_id in {
            "runtime_safety_pass_through_for_draft_output",
            "runtime_safety_redacts_explanation_output",
        }:
            response, _failure_category = _execute_task_case(
                task_id=str(case.input_payload["task_id"]),
                case=case,
            )
            if response is None:
                return (
                    "Safety runtime task execution failed unexpectedly.",
                    EvaluationCaseOutcome.FAIL,
                    ["service://ai/tasks/execute"],
                )
            checks = [
                response.status.value == case.expected_payload["task_status"],
                response.audit.safety.disposition.value == case.expected_payload["disposition"],
                response.audit.safety.runtime_redaction_active
                == case.expected_payload["runtime_redaction_active"],
            ]
            if case.expected_payload.get("caller_app_redacted") is True:
                checks.append("caller_app" not in response.result.structured_output)
            outcome = EvaluationCaseOutcome.PASS if all(checks) else EvaluationCaseOutcome.FAIL
            return (
                (
                    "Task execution reflected the expected runtime safety outcome."
                    if outcome == EvaluationCaseOutcome.PASS
                    else "Task execution did not reflect the expected runtime safety outcome."
                ),
                outcome,
                ["service://ai/tasks/execute", "service://platform/safety/runtime-status"],
            )
        safety_outcome, runtime_redaction_active = _execute_direct_safety_case(case=case)
        checks = [
            safety_outcome.disposition.value == case.expected_payload["disposition"],
            runtime_redaction_active == case.expected_payload["runtime_redaction_active"],
        ]
        outcome = EvaluationCaseOutcome.PASS if all(checks) else EvaluationCaseOutcome.FAIL
        return (
            (
                "Direct safety enforcement matched the expected blocked or degraded runtime behavior."
                if outcome == EvaluationCaseOutcome.PASS
                else "Direct safety enforcement did not match the expected blocked or degraded runtime behavior."
            ),
            outcome,
            ["service://platform/safety/runtime-status", "service://ai/tasks/execute"],
        )

    return (
        f"Fixture family '{fixture_id}' does not yet have runtime-backed execution semantics.",
        EvaluationCaseOutcome.FAIL,
        [f"fixture://{fixture_id}"],
    )


def _evaluate_capability_pack_case(
    *,
    fixture_task_id: str,
    pack_id: str,
    failure_label: str,
    pass_summary: str,
    fail_summary: str,
    case: EvaluationFixtureRuntimeCase,
) -> tuple[str, EvaluationCaseOutcome, list[str]]:
    task_id = str(case.input_payload.get("task_id", fixture_task_id))
    response, failure_category = _execute_task_case(task_id=task_id, case=case)
    if response is None:
        return (
            f"{failure_label} failed unexpectedly with '{failure_category}'.",
            EvaluationCaseOutcome.FAIL,
            [
                f"service://platform/capability-packs/{pack_id}",
                "service://ai/tasks/execute",
            ],
        )
    caller_visible_in_payload = "caller_app" in response.result.structured_output
    checks = [
        response.output_label.value == case.expected_payload["output_label"],
        response.audit.authorization.outcome.value
        == case.expected_payload["authorization_outcome"],
        response.audit.authorization.caller_app == case.expected_payload["caller_app"],
        response.audit.authorization.task_id == case.expected_payload["task_id"],
        response.audit.safety.disposition.value == case.expected_payload["safety_disposition"],
        caller_visible_in_payload == case.expected_payload["caller_visible_in_payload"],
        response.audit.stubbed is bool(case.expected_payload["stubbed"]),
    ]
    outcome = EvaluationCaseOutcome.PASS if all(checks) else EvaluationCaseOutcome.FAIL
    return (
        pass_summary if outcome == EvaluationCaseOutcome.PASS else fail_summary,
        outcome,
        [
            f"service://platform/capability-packs/{pack_id}",
            "service://ai/tasks/execute",
        ],
    )


def _execute_task_case(
    *,
    task_id: str,
    case: EvaluationFixtureRuntimeCase,
) -> tuple[TaskExecutionResponse | None, str | None]:
    caller_app = _resolve_eval_caller_app(task_id=task_id, case=case)
    try:
        response = execute_task(
            TaskExecutionRequest(
                task_id=task_id,
                input_mode=TaskInputMode.STRUCTURED_CONTEXT,
                caller=CallerMetadata(
                    caller_app=caller_app,
                    correlation_id=case.input_payload.get("correlation_id", f"eval-{case.case_id}"),
                    tenant_id=_default_eval_tenant_id(
                        caller_app=caller_app,
                        case_tenant_id=case.input_payload.get("tenant_id"),
                    ),
                ),
                context=TaskContextEnvelope(
                    summary=case.summary,
                    payload=_build_task_payload(case=case),
                    source_refs=[],
                ),
                expected_output_label=(
                    OutputLabel.RETRIEVAL_ANSWER if task_id.startswith("knowledge_") else None
                ),
            )
        )
        return (response, None)
    except HTTPException as exc:
        detail = str(exc.detail)
        failure_category = detail.split(":", 1)[0] if ":" in detail else detail
        return (None, failure_category)


def _resolve_eval_caller_app(*, task_id: str, case: EvaluationFixtureRuntimeCase) -> str:
    configured_caller_app = case.input_payload.get("caller_app")
    if (
        isinstance(configured_caller_app, str)
        and configured_caller_app
        and configured_caller_app != "lotus-ai"
    ):
        return configured_caller_app
    if task_id.startswith("knowledge_"):
        return "lotus-workbench"
    return "lotus-manage"


def _build_task_payload(*, case: EvaluationFixtureRuntimeCase) -> dict[str, object]:
    payload = {
        key: value
        for key, value in case.input_payload.items()
        if key
        not in {
            "caller_app",
            "correlation_id",
            "tenant_id",
            "task_id",
            "retrieval_mode",
            "index_sources",
            "safety_mode",
            "promote_request",
            "rollback_request",
        }
    }
    if "source_filters" in payload and "source_ids" not in payload:
        payload["source_ids"] = payload.pop("source_filters")
    payload["evaluation_case_id"] = case.case_id
    return payload


def _default_eval_tenant_id(*, caller_app: str, case_tenant_id: object | None) -> str | None:
    if isinstance(case_tenant_id, str) and case_tenant_id:
        return case_tenant_id
    if caller_app == "lotus-manage":
        return "tenant-sg-001"
    if caller_app == "lotus-advise":
        return "tenant-us-002"
    return None


@contextmanager
def _apply_case_configuration(input_payload: dict[str, object]) -> Iterator[None]:
    original_values = {
        "provider_mode": settings.provider_mode,
        "provider_rollout_state": settings.provider_rollout_state,
        "live_text_provider_id": settings.live_text_provider_id,
        "live_text_model_id": settings.live_text_model_id,
        "live_text_provider_api_key": settings.live_text_provider_api_key,
        "live_text_api_base": settings.live_text_api_base,
        "live_text_allowed_task_ids": settings.live_text_allowed_task_ids,
        "live_text_quota_enforced": settings.live_text_quota_enforced,
        "live_text_default_quota_limit": settings.live_text_default_quota_limit,
        "live_text_task_quota_limits": settings.live_text_task_quota_limits,
        "live_text_budget_enforced": settings.live_text_budget_enforced,
        "live_text_soft_budget_usd": settings.live_text_soft_budget_usd,
        "live_text_degraded_failure_count_threshold": settings.live_text_degraded_failure_count_threshold,
        "live_text_circuit_open_failure_count_threshold": settings.live_text_circuit_open_failure_count_threshold,
        "live_text_circuit_open_seconds": settings.live_text_circuit_open_seconds,
        "live_text_hard_budget_usd": settings.live_text_hard_budget_usd,
        "live_text_input_cost_per_1k_tokens": settings.live_text_input_cost_per_1k_tokens,
        "live_text_output_cost_per_1k_tokens": settings.live_text_output_cost_per_1k_tokens,
        "live_text_degradation_enforced": settings.live_text_degradation_enforced,
        "provider_operations_store_mode": settings.provider_operations_store_mode,
        "retrieval_mode": settings.retrieval_mode,
        "safety_mode": settings.safety_mode,
        "embedding_provider_mode": settings.embedding_provider_mode,
        "live_embedding_provider_id": settings.live_embedding_provider_id,
        "live_embedding_model_id": settings.live_embedding_model_id,
        "live_embedding_provider_api_key": settings.live_embedding_provider_api_key,
    }
    try:
        with ExitStack() as stack:
            reset_prompt_store_cache()
            reset_retrieval_repository()
            reset_provider_operations_store_cache()
            reset_provider_quota_counters()
            reset_provider_degradation_state()
            if "retrieval_mode" in input_payload:
                settings.retrieval_mode = str(input_payload["retrieval_mode"])
            if "safety_mode" in input_payload:
                settings.safety_mode = str(input_payload["safety_mode"])
            if "embedding_provider_mode" in input_payload:
                settings.embedding_provider_mode = str(input_payload["embedding_provider_mode"])
            if "live_embedding_provider_id" in input_payload:
                settings.live_embedding_provider_id = (
                    str(input_payload["live_embedding_provider_id"])
                    if input_payload["live_embedding_provider_id"] is not None
                    else None
                )
            if "live_embedding_model_id" in input_payload:
                settings.live_embedding_model_id = (
                    str(input_payload["live_embedding_model_id"])
                    if input_payload["live_embedding_model_id"] is not None
                    else None
                )
            if "live_embedding_provider_api_key" in input_payload:
                settings.live_embedding_provider_api_key = (
                    str(input_payload["live_embedding_provider_api_key"])
                    if input_payload["live_embedding_provider_api_key"] is not None
                    else None
                )
            indexed_sources = input_payload.get("index_sources", [])
            if isinstance(indexed_sources, list):
                repository = get_retrieval_repository()
                for source_id in indexed_sources:
                    if isinstance(source_id, str):
                        repository.set_source_index_status(
                            source_id=source_id,
                            index_status="INDEXED",
                        )
            if "configured_mode" in input_payload:
                settings.provider_mode = str(input_payload["configured_mode"])
            if "provider_mode" in input_payload:
                settings.provider_mode = str(input_payload["provider_mode"])
            if "rollout_state" in input_payload:
                settings.provider_rollout_state = str(input_payload["rollout_state"])
            if (
                input_payload.get("provider_operations_store_mode") == "sqlalchemy"
                and settings.database_url
            ):
                settings.provider_operations_store_mode = "sqlalchemy"
                reset_provider_operations_store_cache()
            live_execution_signals = any(
                key in input_payload
                for key in (
                    "request_limit",
                    "hard_budget_usd",
                    "tracked_spend_usd",
                    "recorded_spend_usd",
                    "degraded_failure_count_threshold",
                    "circuit_open_seconds",
                )
            )
            if settings.provider_mode == "openai" and (
                input_payload.get("rollout_state") in {"CANARY_ENABLED", "ROLLED_OUT"}
                or live_execution_signals
            ):
                if "rollout_state" not in input_payload:
                    settings.provider_rollout_state = "CANARY_ENABLED"
                settings.live_text_provider_id = "text.openai"
                settings.live_text_model_id = "gpt-5.4"
                settings.live_text_provider_api_key = "eval-secret"
                settings.live_text_allowed_task_ids = str(input_payload.get("task_id", ""))
            if settings.provider_mode == "local_openai_compatible":
                if "rollout_state" not in input_payload:
                    settings.provider_rollout_state = "CANARY_ENABLED"
                settings.live_text_provider_id = "text.local"
                settings.live_text_model_id = str(
                    input_payload.get("live_text_model_id", "qwen3:8b")
                )
                settings.live_text_api_base = str(
                    input_payload.get("live_text_api_base", "http://ollama:11434/v1")
                )
                settings.live_text_provider_api_key = (
                    str(input_payload["live_text_provider_api_key"])
                    if input_payload.get("live_text_provider_api_key") is not None
                    else None
                )
                settings.live_text_allowed_task_ids = str(input_payload.get("task_id", ""))
                local_probe_status = input_payload.get("local_probe_status")
                if isinstance(local_probe_status, dict):
                    stack.enter_context(
                        _patch_target(
                            "app.services.provider_live_execution_state.build_local_openai_compatible_endpoint_status",
                            lambda: type(
                                "ProbeStatus",
                                (),
                                {
                                    "endpoint_reachable": bool(
                                        local_probe_status.get("endpoint_reachable", False)
                                    ),
                                    "model_available": bool(
                                        local_probe_status.get("model_available", False)
                                    ),
                                    "blocking_reason": local_probe_status.get("blocking_reason"),
                                },
                            )(),
                        )
                    )
                local_provider_response = input_payload.get("local_provider_response")
                if isinstance(local_provider_response, dict):
                    stack.enter_context(
                        _patch_target(
                            "app.providers.openai_compatible_text_transport.post_openai_compatible_response",
                            lambda **_: local_provider_response,
                        )
                    )
                local_provider_error = input_payload.get("local_provider_error")
                if isinstance(local_provider_error, dict):
                    failure_category = ProviderFailureCategory(
                        str(local_provider_error["failure_category"])
                    )
                    stack.enter_context(
                        _patch_target(
                            "app.providers.openai_compatible_text_transport.post_openai_compatible_response",
                            lambda **_: _raise_provider_execution_error(
                                category=failure_category,
                                message=str(local_provider_error["message"]),
                            ),
                        )
                    )
            if "request_limit" in input_payload and input_payload.get("quota_scope") == "task":
                settings.live_text_quota_enforced = True
                settings.live_text_task_quota_limits = f"{input_payload['task_id']}={int(cast(int | str, input_payload['request_limit']))}"
                get_provider_operations_store().increment_quota_state(
                    scope=ProviderQuotaScope.TASK,
                    scope_key=str(input_payload["task_id"]),
                    amount=int(cast(int | str, input_payload["request_limit"])),
                    updated_at=_utcnow_iso(),
                )
            if "hard_budget_usd" in input_payload:
                settings.live_text_budget_enforced = True
                settings.live_text_hard_budget_usd = float(
                    cast(int | float | str, input_payload["hard_budget_usd"])
                )
                settings.live_text_soft_budget_usd = float(
                    cast(
                        int | float | str,
                        input_payload.get(
                            "recorded_spend_usd", input_payload.get("tracked_spend_usd", 0.5)
                        ),
                    )
                )
                settings.live_text_input_cost_per_1k_tokens = 0.01
                settings.live_text_output_cost_per_1k_tokens = 0.03
                tracked_spend = float(
                    cast(
                        int | float | str,
                        input_payload.get(
                            "tracked_spend_usd", input_payload.get("recorded_spend_usd", 0.0)
                        ),
                    )
                )
                if tracked_spend > 0:
                    get_provider_operations_store().add_budget_spend(
                        budget_key="live_text_generation",
                        amount_usd=tracked_spend,
                        updated_at=_utcnow_iso(),
                    )
                    if settings.provider_operations_store_mode == "sqlalchemy":
                        reset_provider_operations_store_cache()
            if "degraded_failure_count_threshold" in input_payload:
                settings.live_text_degradation_enforced = True
                settings.live_text_degraded_failure_count_threshold = int(
                    cast(int | str, input_payload["degraded_failure_count_threshold"])
                )
            if "circuit_open_failure_count_threshold" in input_payload:
                settings.live_text_circuit_open_failure_count_threshold = int(
                    cast(int | str, input_payload["circuit_open_failure_count_threshold"])
                )
            if "circuit_open_seconds" in input_payload:
                settings.live_text_circuit_open_seconds = int(
                    cast(int | str, input_payload["circuit_open_seconds"])
                )
            elif any(
                key in input_payload
                for key in (
                    "degraded_failure_count_threshold",
                    "circuit_open_failure_count_threshold",
                )
            ):
                settings.live_text_circuit_open_seconds = 60
            if "degraded_failure_count_threshold" in input_payload:
                failure_count = int(
                    cast(int | str, input_payload["degraded_failure_count_threshold"])
                )
                for _ in range(failure_count):
                    record_provider_failure(ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR)
                if settings.provider_operations_store_mode == "sqlalchemy":
                    reset_provider_operations_store_cache()
            elif "circuit_open_seconds" in input_payload:
                settings.live_text_degradation_enforced = True
                settings.live_text_degraded_failure_count_threshold = 1
                settings.live_text_circuit_open_failure_count_threshold = 1
                record_provider_failure(ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR)
                if settings.provider_operations_store_mode == "sqlalchemy":
                    reset_provider_operations_store_cache()
            yield
    finally:
        for key, value in original_values.items():
            setattr(settings, key, value)
        reset_retrieval_repository()
        reset_prompt_store_cache()
        reset_provider_operations_store_cache()
        reset_provider_quota_counters()
        reset_provider_degradation_state()


@contextmanager
def _patch_target(target: str, replacement: object) -> Iterator[None]:
    from unittest.mock import patch

    with patch(target, replacement):
        yield


def _raise_provider_execution_error(*, category: ProviderFailureCategory, message: str) -> Any:
    from app.providers.base import ProviderExecutionError

    raise ProviderExecutionError(category=category, message=message)


def _apply_prompt_transition_for_evaluation(
    *,
    task_id: str,
    candidate_prompt_version: str,
    requested_by: str,
    approved_by: str,
    reason: str,
) -> None:
    repository = get_prompt_repository()
    rollout_state = repository.get_prompt_rollout_state(task_id)
    if rollout_state is None:
        raise HTTPException(
            status_code=404,
            detail=f"Prompt rollout state for task '{task_id}' was not found.",
        )
    candidate_prompt = repository.get_prompt_version(task_id, candidate_prompt_version)
    if candidate_prompt is None:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate prompt version '{candidate_prompt_version}' was not found.",
        )
    if candidate_prompt.lifecycle_status != PromptLifecycleStatus.CANDIDATE:
        raise HTTPException(
            status_code=409,
            detail=f"Prompt version '{candidate_prompt_version}' is not a governed candidate.",
        )
    active_prompt = repository.get_prompt_version(task_id, rollout_state.active_prompt_version)
    if active_prompt is None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Prompt rollout state for task '{task_id}' references missing active prompt "
                f"'{rollout_state.active_prompt_version}'."
            ),
        )
    updated_state = PromptRolloutStateRecord(
        task_id=task_id,
        active_prompt_version=candidate_prompt.prompt_version,
        candidate_prompt_version=None,
        previous_active_prompt_version=active_prompt.prompt_version,
        rollout_mode=PromptRolloutSelectionMode.GOVERNED_CONTROL_ACTIONS,
        runtime_mutation_enabled=True,
    )
    event = PromptRolloutEventRecord(
        event_id=f"prompt_evt_eval_{candidate_prompt.prompt_version.replace('.', '_')}",
        task_id=task_id,
        action_type=PromptControlActionType.PROMOTE_CANDIDATE,
        requested_by=requested_by,
        approved_by=approved_by,
        reason=reason,
        prior_active_prompt_version=active_prompt.prompt_version,
        resulting_active_prompt_version=candidate_prompt.prompt_version,
        prior_candidate_prompt_version=rollout_state.candidate_prompt_version,
        resulting_candidate_prompt_version=None,
        authorization=_evaluation_control_authorization(
            capability_type=AuthorizationCapabilityType.PROMPT_CONTROL,
            task_id=task_id,
        ),
        recorded_at=_utcnow_iso(),
    )
    repository.save_prompt_rollout_transition(
        rollout_state=updated_state,
        updated_prompts=[
            active_prompt.model_copy(update={"lifecycle_status": PromptLifecycleStatus.RETIRED}),
            candidate_prompt.model_copy(update={"lifecycle_status": PromptLifecycleStatus.ACTIVE}),
        ],
        event=event,
    )


def _apply_prompt_rollback_for_evaluation(
    *,
    task_id: str,
    requested_by: str,
    approved_by: str,
    reason: str,
) -> None:
    repository = get_prompt_repository()
    rollout_state = repository.get_prompt_rollout_state(task_id)
    if rollout_state is None:
        raise HTTPException(
            status_code=404,
            detail=f"Prompt rollout state for task '{task_id}' was not found.",
        )
    if rollout_state.previous_active_prompt_version is None:
        raise HTTPException(
            status_code=409,
            detail=f"Prompt rollout state for task '{task_id}' has no prior active prompt.",
        )
    active_prompt = repository.get_prompt_version(task_id, rollout_state.active_prompt_version)
    previous_active_prompt = repository.get_prompt_version(
        task_id, rollout_state.previous_active_prompt_version
    )
    if active_prompt is None or previous_active_prompt is None:
        raise HTTPException(
            status_code=409,
            detail=f"Prompt rollback references missing prompt versions for task '{task_id}'.",
        )
    updated_state = PromptRolloutStateRecord(
        task_id=task_id,
        active_prompt_version=previous_active_prompt.prompt_version,
        candidate_prompt_version=active_prompt.prompt_version,
        previous_active_prompt_version=None,
        rollout_mode=PromptRolloutSelectionMode.GOVERNED_CONTROL_ACTIONS,
        runtime_mutation_enabled=True,
    )
    event = PromptRolloutEventRecord(
        event_id=f"prompt_evt_eval_rollback_{previous_active_prompt.prompt_version.replace('.', '_')}",
        task_id=task_id,
        action_type=PromptControlActionType.ROLLBACK_TO_PREVIOUS_ACTIVE,
        requested_by=requested_by,
        approved_by=approved_by,
        reason=reason,
        prior_active_prompt_version=active_prompt.prompt_version,
        resulting_active_prompt_version=previous_active_prompt.prompt_version,
        prior_candidate_prompt_version=rollout_state.candidate_prompt_version,
        resulting_candidate_prompt_version=active_prompt.prompt_version,
        authorization=_evaluation_control_authorization(
            capability_type=AuthorizationCapabilityType.PROMPT_CONTROL,
            task_id=task_id,
        ),
        recorded_at=_utcnow_iso(),
    )
    repository.save_prompt_rollout_transition(
        rollout_state=updated_state,
        updated_prompts=[
            active_prompt.model_copy(update={"lifecycle_status": PromptLifecycleStatus.CANDIDATE}),
            previous_active_prompt.model_copy(
                update={"lifecycle_status": PromptLifecycleStatus.ACTIVE}
            ),
        ],
        event=event,
    )


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _evaluation_control_authorization(
    *,
    capability_type: AuthorizationCapabilityType,
    task_id: str | None = None,
) -> AuthorizationDecision:
    return AuthorizationDecision(
        caller_app="lotus-platform",
        capability_type=capability_type,
        outcome=AuthorizationOutcome.ALLOWED,
        allowed=True,
        tenant_policy_mode=TenantPolicyMode.OPTIONAL,
        task_id=task_id,
        requested_source_ids=[],
        effective_source_ids=[],
        tenant_id=None,
        summary="Evaluation fixture recorded an allowed control-plane authorization decision.",
    )


def _execute_direct_safety_case(
    *, case: EvaluationFixtureRuntimeCase
) -> tuple[SafetyExecutionOutcome, bool]:
    from app.contracts.providers import ProviderExecutionResponse
    from app.contracts.tasks import OutputLabel

    provider_execution = ProviderExecutionResponse(
        provider_id="text.stub",
        provider_mode="stub",
        stubbed=True,
        message=str(case.input_payload["provider_message"]),
        structured_output=cast(dict[str, object], case.input_payload["provider_structured_output"]),
    )
    policy = resolve_safety_policy_for_output(OutputLabel(case.input_payload["output_label"]))
    _safe_execution, outcome = apply_safety_enforcement(
        policy=policy,
        provider_execution=provider_execution,
    )
    return outcome, outcome.runtime_redaction_active
