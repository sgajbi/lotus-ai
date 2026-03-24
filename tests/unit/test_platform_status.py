from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch

from app.config import settings
from app.contracts.providers import ProviderFailureCategory
from app.repositories.evaluation_runtime_repository import EvaluationRunRecord
from app.services.platform_status import (
    _resolve_startup_readiness_state,
    build_platform_runtime_status,
)
from app.services.evaluation_runtime_store import (
    get_evaluation_runtime_store,
    reset_evaluation_runtime_store_cache,
)
from app.services.prompt_rollout_control import apply_prompt_control_action
from app.services.prompt_store import reset_prompt_store_cache
from app.services.provider_degradation_state import record_provider_failure
from app.contracts.prompts import PromptControlActionRequest, PromptControlActionType
from app.services.provider_operations_store import reset_provider_operations_store_cache
from tests.support.migration_runner import upgrade_database_to_head


def test_resolve_startup_readiness_state_defaults_when_app_state_missing() -> None:
    startup_state = _resolve_startup_readiness_state(None)

    assert startup_state.blocking is False
    assert startup_state.warnings == []


def test_resolve_startup_readiness_state_reads_blocking_and_findings() -> None:
    startup_state = _resolve_startup_readiness_state(
        SimpleNamespace(
            startup_readiness_blocking=True,
            startup_readiness_findings=["retrieval store: migration required"],
        )
    )

    assert startup_state.blocking is True
    assert startup_state.warnings == ["retrieval store: migration required"]


def test_build_platform_runtime_status_includes_startup_readiness_state() -> None:
    status = build_platform_runtime_status(
        SimpleNamespace(
            startup_readiness_blocking=True,
            startup_readiness_findings=["audit store: configuration required"],
        )
    )

    assert status.service == "lotus-ai"
    assert status.async_runtime.cutover_state == "in_process_only"
    assert status.async_runtime.queue_mode == "DISABLED"
    assert status.async_runtime.queue_backend == "none"
    assert status.async_runtime.worker_mode == "IN_PROCESS_ONLY"
    assert status.async_runtime.active_worker_execution == "in_process_stub"
    assert status.async_runtime.enqueued_job_count == 0
    assert status.provider_governance.blocking_area_count == 3
    assert status.provider_operations.operations_state.value == "ROLLOUT_BLOCKED"
    assert status.retrieval_governance.blocking_area_count == 3
    assert status.prompt_governance.blocking_area_count == 2
    assert status.prompt_runtime.rollout_mode.value == "GOVERNED_CONTROL_ACTIONS"
    assert status.prompt_runtime.candidate_prompt_count == 0
    assert any(state.task_id == "explain.v1" for state in status.prompt_runtime.rollout_states)
    assert status.evaluation_runtime.manifest_version == "foundation.v1"
    assert status.evaluation_runtime.approval_gates[0].domain_id == "prompt_rollout"
    assert status.evaluation_runtime.approval_gates[1].domain_id == "retrieval_execution"
    assert status.evaluation_runtime.approval_gates[2].domain_id == "provider_execution"
    assert status.evaluation_runtime.approval_gates[3].domain_id == "safety_enforcement"
    assert status.task_runtime.enabled_task_count >= 7
    assert status.task_runtime.retrieval_backed_task_count == 2
    assert status.task_runtime.tasks[0].task_id == "explain.v1"
    assert status.safety_runtime.runtime_redaction_active is False
    assert status.safety_governance.governance_ready is False
    assert status.safety_governance.blocking_area_count == 3
    assert status.safety_governance.runbook_readiness.runbook_ready is False
    assert (
        status.safety_governance.evidence_readiness.approval_gate.domain_id == "safety_enforcement"
    )
    assert status.startup_readiness_blocking is True
    assert status.startup_readiness_warnings == ["audit store: configuration required"]


def test_build_platform_runtime_status_reports_dedicated_async_worker_cutover() -> None:
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"

    status = build_platform_runtime_status(None)

    assert status.async_runtime.cutover_state == "dedicated_workers_active"
    assert status.async_runtime.queue_mode == "ACTIVE"
    assert status.async_runtime.queue_backend == "redis_queue"
    assert status.async_runtime.worker_mode == "DEDICATED"
    assert status.async_runtime.active_worker_execution == "queue_backed_workers"


def test_build_platform_runtime_status_reflects_durable_provider_operations_posture(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-platform-status.db'}"
    settings.provider_mode = "openai"
    settings.provider_rollout_state = "CANARY_ENABLED"
    settings.live_text_provider_id = "text.openai"
    settings.live_text_model_id = "gpt-5.4"
    settings.live_text_provider_api_key = "secret"
    settings.live_text_allowed_task_ids = "explain.v1"
    settings.live_text_degradation_enforced = True
    settings.live_text_degraded_failure_count_threshold = 1
    settings.live_text_circuit_open_failure_count_threshold = 2
    settings.live_text_circuit_open_seconds = 60
    upgrade_database_to_head(settings.database_url)

    fixed_now = datetime(2026, 3, 23, 12, 0, tzinfo=UTC)
    monkeypatch.setattr("app.services.provider_degradation_state._utcnow", lambda: fixed_now)

    record_provider_failure(ProviderFailureCategory.PROVIDER_TIMEOUT)
    record_provider_failure(ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR)
    reset_provider_operations_store_cache()

    status = build_platform_runtime_status(None)

    assert status.provider_operations.operations_state.value == "CIRCUIT_OPEN"
    assert status.provider_operations.degradation_status.status == "CIRCUIT_OPEN"
    assert status.provider_operations.degradation_status.timeout_failure_count == 1
    assert status.provider_operations.degradation_status.upstream_error_failure_count == 1


def test_build_platform_runtime_status_reflects_sql_backed_prompt_rollout_after_restart(
    tmp_path: Path,
) -> None:
    settings.prompt_store_mode = "sqlalchemy"
    settings.evaluation_runtime_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-prompt-platform-status.db'}"
    upgrade_database_to_head(settings.database_url)

    for fixture_id in ("prompt_promotion_examples", "prompt_rollback_examples"):
        get_evaluation_runtime_store().save_run(
            EvaluationRunRecord(
                run_id=f"runtime_prompt_platform_{fixture_id}",
                fixture_id=fixture_id,
                manifest_version="foundation.v1",
                lifecycle_status="COMPLETED",
                triggered_by="operator-a",
                submitted_at="2026-03-24T09:00:00Z",
                async_job_id=f"async_prompt_platform_{fixture_id}",
                latest_message="Prompt approval fixture passed.",
                verdict="PASS",
                case_count=1,
            )
        )

    apply_prompt_control_action(
        PromptControlActionRequest(
            task_id="explain.v1",
            action_type=PromptControlActionType.PROMOTE_CANDIDATE,
            candidate_prompt_version="foundation.explain.v2",
            requested_by="alice@lotus.test",
            approved_by="bob@lotus.test",
            reason="Promote prompt for restart-survival test",
        )
    )

    reset_prompt_store_cache()
    reset_evaluation_runtime_store_cache()

    status = build_platform_runtime_status(None)

    explain_selection = next(
        selection
        for selection in status.prompt_runtime.selections
        if selection.task_id == "explain.v1"
    )
    explain_state = next(
        state for state in status.prompt_runtime.rollout_states if state.task_id == "explain.v1"
    )

    assert status.prompt_governance.activation_readiness.activation_ready is True
    assert status.prompt_governance.runbook_readiness.runbook_ready is True
    assert explain_selection.prompt_version == "foundation.explain.v2"
    assert explain_state.active_prompt_version == "foundation.explain.v2"
    assert explain_state.previous_active_prompt_version == "foundation.explain.v1"
    assert explain_state.latest_control_event is not None
    assert (
        explain_state.latest_control_event.action_type == PromptControlActionType.PROMOTE_CANDIDATE
    )
