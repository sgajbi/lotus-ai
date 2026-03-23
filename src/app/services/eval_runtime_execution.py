from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterator, cast

from fastapi import HTTPException

from app.config import settings
from app.contracts.evals import EvaluationCaseOutcome, EvaluationRunVerdict
from app.contracts.providers import ProviderFailureCategory, ProviderQuotaScope
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
from app.services.evaluation_runtime_store import get_evaluation_runtime_store
from app.services.provider_budget_policy import build_provider_budget_policy
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
from app.services.retrieval_execution_status import build_retrieval_execution_status
from app.services.retrieval_store import get_retrieval_repository, reset_retrieval_repository
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
    return EvaluationCaseResultRecord(
        case_result_id=f"{attempt_id}_{case.case_id}",
        run_id=run.run_id,
        attempt_id=attempt_id,
        case_id=case.case_id,
        fixture_id=run.fixture_id,
        outcome=outcome.value,
        summary=summary,
        evidence_refs=evidence_refs,
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
            controls_present = (
                response is not None
                and response.result.structured_output.get("timeout_ms") is not None
            )
            stubbed = response is not None and response.audit.stubbed is True
            outcome = (
                EvaluationCaseOutcome.PASS
                if controls_present and stubbed
                else EvaluationCaseOutcome.FAIL
            )
            return (
                (
                    "Task execution preserved bounded provider controls in stub runtime."
                    if outcome == EvaluationCaseOutcome.PASS
                    else "Task execution did not preserve the expected bounded provider controls."
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

    return (
        f"Fixture family '{fixture_id}' does not yet have runtime-backed execution semantics.",
        EvaluationCaseOutcome.FAIL,
        [f"fixture://{fixture_id}"],
    )


def _execute_task_case(
    *,
    task_id: str,
    case: EvaluationFixtureRuntimeCase,
) -> tuple[TaskExecutionResponse | None, str | None]:
    try:
        response = execute_task(
            TaskExecutionRequest(
                task_id=task_id,
                input_mode=TaskInputMode.STRUCTURED_CONTEXT,
                caller=CallerMetadata(
                    caller_app=case.input_payload.get("caller_app", "lotus-ai"),
                    correlation_id=case.input_payload.get("correlation_id", f"eval-{case.case_id}"),
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


def _build_task_payload(*, case: EvaluationFixtureRuntimeCase) -> dict[str, object]:
    payload = {
        key: value
        for key, value in case.input_payload.items()
        if key not in {"caller_app", "correlation_id", "task_id", "retrieval_mode", "index_sources"}
    }
    if "source_filters" in payload and "source_ids" not in payload:
        payload["source_ids"] = payload.pop("source_filters")
    payload["evaluation_case_id"] = case.case_id
    return payload


@contextmanager
def _apply_case_configuration(input_payload: dict[str, object]) -> Iterator[None]:
    original_values = {
        "provider_mode": settings.provider_mode,
        "provider_rollout_state": settings.provider_rollout_state,
        "live_text_provider_id": settings.live_text_provider_id,
        "live_text_model_id": settings.live_text_model_id,
        "live_text_provider_api_key": settings.live_text_provider_api_key,
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
    }
    try:
        reset_retrieval_repository()
        reset_provider_operations_store_cache()
        reset_provider_quota_counters()
        reset_provider_degradation_state()
        if "retrieval_mode" in input_payload:
            settings.retrieval_mode = str(input_payload["retrieval_mode"])
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
        if "request_limit" in input_payload and input_payload.get("quota_scope") == "task":
            settings.live_text_quota_enforced = True
            settings.live_text_task_quota_limits = (
                f"{input_payload['task_id']}={int(cast(int | str, input_payload['request_limit']))}"
            )
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
            failure_count = int(cast(int | str, input_payload["degraded_failure_count_threshold"]))
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
        reset_provider_operations_store_cache()
        reset_provider_quota_counters()
        reset_provider_degradation_state()


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
