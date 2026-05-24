from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from _pytest.monkeypatch import MonkeyPatch

from app.config import settings
from app.contracts.providers import ProviderFailureCategory
from app.contracts.runtime_readiness import RuntimeReadinessStatus, StoreRuntimeStatusDescriptor
from app.repositories.evaluation_runtime_repository import EvaluationRunRecord
from app.services.artifact_store import reset_artifact_store_cache
from app.services.async_delivery_queue import get_test_async_delivery_queue
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
    settings.deployment_split_stage = "unified"
    settings.artifact_store_mode = "memory"
    settings.artifact_object_store_mode = "memory"
    settings.artifact_object_store_root = None
    reset_artifact_store_cache()

    status = build_platform_runtime_status(
        SimpleNamespace(
            startup_readiness_blocking=True,
            startup_readiness_findings=["audit store: configuration required"],
        )
    )

    assert status.service == "lotus-ai"
    assert status.access_control_store_mode == "memory"
    assert status.workflow_pack_registry_store_mode == "memory"
    assert status.workflow_pack_task_flow_store_mode == "memory"
    assert status.workflow_pack_runtime.registration_count == 11
    assert status.workflow_pack_runtime.registered_count == 10
    assert status.workflow_pack_runtime.execution_binding_count == 10
    assert status.workflow_pack_runtime.executable_registration_count == 10
    assert status.workflow_pack_runtime.executable_review_required_count == 10
    assert status.workflow_pack_runtime.executable_without_review_count == 0
    assert status.workflow_pack_runtime.registered_without_execution_binding_count == 0
    assert status.workflow_pack_runtime.executable_registration_refs == [
        "advisor_brief.pack@v1",
        "dpm_exception_summary.pack@v1",
        "dpm_operations_handoff_summary.pack@v1",
        "dpm_pm_memo.pack@v1",
        "dpm_wave_pm_memo.pack@v1",
        "outcome_review_narrative.pack@v1",
        "pm_quality_summary.pack@v1",
        "proposal_memo_commentary.pack@v1",
        "twr_inspection_support_brief.pack@v1",
        "workspace_rationale.pack@v1",
    ]
    assert status.workflow_pack_runtime.executable_review_required_refs == [
        "advisor_brief.pack@v1",
        "dpm_exception_summary.pack@v1",
        "dpm_operations_handoff_summary.pack@v1",
        "dpm_pm_memo.pack@v1",
        "dpm_wave_pm_memo.pack@v1",
        "outcome_review_narrative.pack@v1",
        "pm_quality_summary.pack@v1",
        "proposal_memo_commentary.pack@v1",
        "twr_inspection_support_brief.pack@v1",
        "workspace_rationale.pack@v1",
    ]
    assert len(status.workflow_pack_runtime.executable_activity) == 10
    assert [item.registration_ref for item in status.workflow_pack_runtime.executable_activity] == [
        "advisor_brief.pack@v1",
        "dpm_exception_summary.pack@v1",
        "dpm_operations_handoff_summary.pack@v1",
        "dpm_pm_memo.pack@v1",
        "dpm_wave_pm_memo.pack@v1",
        "outcome_review_narrative.pack@v1",
        "pm_quality_summary.pack@v1",
        "proposal_memo_commentary.pack@v1",
        "twr_inspection_support_brief.pack@v1",
        "workspace_rationale.pack@v1",
    ]
    for item in status.workflow_pack_runtime.executable_activity:
        assert item.run_count == 0
        assert item.ready_count == 0
        assert item.action_required_count == 0
        assert item.historical_count == 0
        assert item.latest_action_required_run_id is None
        assert item.latest_ready_run_id is None
        assert item.has_activity is False
    assert status.workflow_pack_runtime.attention_queue.queue_depth == 0
    assert status.workflow_pack_runtime.attention_queue.queue_limit == 5
    assert status.workflow_pack_runtime.attention_queue.items == []
    assert status.workflow_pack_runtime.queue_attention.heartbeat_status == "READY"
    assert status.workflow_pack_runtime.queue_attention.attention_count == 0
    assert status.workflow_pack_runtime.queue_attention.active_admission_count == 0
    assert status.workflow_pack_runtime.queue_attention.queue_source_mode == "memory"
    assert status.workflow_pack_runtime.run_summary.run_count == 0
    assert status.workflow_pack_runtime.run_summary.awaiting_review_count == 0
    assert status.workflow_pack_runtime.run_summary.accepted_count == 0
    assert status.workflow_pack_runtime.run_summary.action_required_count == 0
    assert status.workflow_pack_task_flow_store.mode == "memory"
    assert status.workflow_pack_task_flow_store.status.value == "READY"
    assert status.access_control_runtime.enforcement_state.value == "FULLY_ENFORCED"
    assert status.access_control_runtime.data_plane_enforced is True
    assert status.access_control_runtime.control_plane_enforced is True
    assert status.access_control_runtime.policy_count >= 5
    assert status.access_control_runtime.tenant_isolation_active is True
    assert status.access_control_governance.governance_ready is False
    assert status.access_control_governance.activation_readiness.activation_ready is False
    assert status.access_control_governance.runbook_readiness.runbook_ready is True
    assert status.access_control_governance.blocking_area_count == 1
    assert status.artifact_store_mode == "memory"
    assert status.artifact_object_store_mode == "memory"
    assert status.artifact_runtime.metadata_store_mode == "memory"
    assert status.artifact_runtime.object_store_mode == "memory"
    assert status.artifact_runtime.artifact_count >= 0
    assert status.artifact_governance.governance_ready is False
    assert status.artifact_governance.activation_readiness.activation_ready is False
    assert status.artifact_governance.runbook_readiness.runbook_ready is True
    assert status.observability_runtime.domain_count == 6
    assert status.observability_runtime.unavailable_domain_count == 0
    assert status.observability_runtime.incident_evidence_supported_domain_count >= 1
    assert status.observability_runtime.ai_surface_supportability.supported_surface_count == 10
    assert (
        status.observability_runtime.ai_surface_supportability.executable_workflow_pack_count == 10
    )
    assert (
        status.observability_runtime.ai_surface_supportability.no_sensitive_content_telemetry
        is False
    )
    assert {
        item.surface_id for item in status.observability_runtime.ai_surface_supportability.surfaces
    } == {
        "advisor_brief",
        "dpm_exception_summary",
        "dpm_operations_handoff_summary",
        "dpm_pm_memo",
        "dpm_wave_pm_memo",
        "outcome_review_narrative",
        "pm_quality_summary",
        "proposal_memo_commentary",
        "twr_inspection_support_brief",
        "workspace_rationale",
    }
    assert status.observability_governance.governance_ready is False
    assert status.observability_governance.activation_readiness.activation_ready is False
    assert status.observability_governance.runbook_readiness.runbook_ready is True
    assert status.observability_governance.blocking_area_count == 1
    assert status.async_runtime.cutover_state == "in_process_only"
    assert status.async_runtime.queue_mode == "DISABLED"
    assert status.async_runtime.queue_backend == "none"
    assert status.async_runtime.worker_mode == "IN_PROCESS_ONLY"
    assert status.async_runtime.active_worker_execution == "in_process_stub"
    assert status.async_runtime.queue_backlog_count == 0
    assert status.async_runtime.drain_mode_active is False
    assert status.async_runtime.enqueued_job_count == 0
    assert status.provider_governance.blocking_area_count == 3
    assert status.provider_operations.operations_state.value == "ROLLOUT_BLOCKED"
    assert status.retrieval_governance.blocking_area_count == 3
    assert status.prompt_governance.blocking_area_count == 2
    assert status.prompt_runtime.rollout_mode.value == "GOVERNED_CONTROL_ACTIONS"
    assert status.prompt_runtime.candidate_prompt_count == 0
    assert any(state.task_id == "explain.v1" for state in status.prompt_runtime.rollout_states)
    assert status.evaluation_runtime.manifest_version == "foundation.v1"
    assert status.evaluation_runtime.approval_gates[0].domain_id == "first_use_case_onboarding"
    assert status.evaluation_runtime.approval_gates[1].domain_id == "prompt_rollout"
    assert status.evaluation_runtime.approval_gates[2].domain_id == "retrieval_execution"
    assert status.evaluation_runtime.approval_gates[3].domain_id == "provider_execution"
    assert status.evaluation_runtime.approval_gates[4].domain_id == "safety_enforcement"
    assert status.evaluation_runtime.approval_gates[5].domain_id == "analytics_commentary_pack"
    assert status.evaluation_runtime.approval_gates[6].domain_id == "decision_explanation_pack"
    assert status.task_runtime.enabled_task_count >= 7
    assert status.task_runtime.retrieval_backed_task_count == 2
    assert status.task_runtime.tasks[0].task_id == "explain.v1"
    assert status.capability_pack_count == 2
    assert status.capability_pack_catalog.pack_count == 2
    assert status.capability_pack_catalog.reusable_pack_count == 1
    assert status.capability_pack_catalog.packs[0].pack_id == "analytics_commentary.pack.v1"
    assert status.capability_pack_catalog.packs[0].maturity_stage.value == "REUSABLE"
    assert status.capability_pack_catalog.packs[1].pack_id == "decision_explanation.pack.v1"
    assert (
        status.capability_pack_catalog.packs[0].quality_gate_domain_id
        == "analytics_commentary_pack"
    )
    assert status.capability_pack_catalog.packs[0].quality_evidence_state.value == "STAGED_ONLY"
    assert status.capability_pack_governance.ready_pack_count == 0
    assert status.capability_pack_governance.blocking_pack_count == 2
    assert status.app_capability_rollout_count == 4
    assert status.app_capability_rollout_ready_count == 1
    assert status.app_capability_rollout_catalog.pairing_count == 4
    assert status.app_capability_rollout_catalog.onboarded_pairing_count == 1
    assert status.app_capability_rollout_catalog.active_pairing_count == 0
    assert status.app_capability_rollout_governance.ready_pairing_count == 1
    assert status.app_capability_rollout_governance.blocking_pairing_count == 3
    assert status.app_capability_rollout_observability.pairing_count == 4
    assert status.app_capability_rollout_observability.blocked_pairing_count == 4
    assert status.app_capability_rollout_observability.observability_ready is True
    assert status.app_capability_rollout_lifecycle.ready_pairing_count == 1
    assert status.app_capability_rollout_lifecycle.blocking_pairing_count == 3
    assert status.app_capability_rollout_observed_count >= 0
    assert status.app_capability_rollout_lifecycle_ready_count == 1
    assert (
        status.app_capability_rollout_catalog.rollout_records[0].downstream_app
        == "lotus-performance"
    )
    assert (
        status.app_capability_rollout_catalog.rollout_records[
            0
        ].capability_pack_maturity_stage.value
        == "REUSABLE"
    )
    assert (
        status.app_capability_rollout_catalog.rollout_records[0].rollout_stage.value
        == "INTEGRATION_IN_PROGRESS"
    )
    assert status.first_use_case.downstream_app == "lotus-performance"
    assert status.first_use_case.capability_pack_id == "analytics_commentary.pack.v1"
    assert status.first_use_case.capability_pack_family_id == "analytics_commentary"
    assert status.first_use_case.task_id == "explain.v1"
    assert status.first_use_case.contract_hardened is True
    assert status.first_use_case_governance.rollout_stage.value == "PRE_PROD_VALIDATION"
    assert status.first_use_case_governance.operational_posture.value == "LIMITED_ROLLOUT_BLOCKED"
    assert status.first_use_case_governance.active_production_ready is False
    assert status.first_use_case_governance.governance_ready is False
    assert status.first_use_case_governance.readiness.readiness_ready is False
    assert status.first_use_case_governance.runbook_readiness.runbook_ready is True
    assert status.deployment_split.configured_stage.value == "UNIFIED"
    assert status.deployment_split.effective_stage.value == "UNIFIED"
    assert status.deployment_split.front_door_plane.value == "runtime"
    assert status.deployment_split.split_ready is False
    assert status.deployment_split.plane_count == 3
    assert status.deployment_split.route_count == 4
    assert status.deployment_split.routes[0].route_mode.value == "UNIFIED_INTERNAL"
    assert status.deployment_split_governance.governance_ready is False
    assert status.deployment_split_governance.activation_readiness.activation_ready is True
    assert status.deployment_split_governance.runbook_readiness.runbook_ready is True
    assert status.deployment_split_governance.observability_governance_ready is False
    assert status.evaluation_runtime.owning_plane.value == "runtime"
    assert status.evaluation_runtime.submission_route_mode.value == "UNIFIED_INTERNAL"
    assert status.evaluation_runtime.async_execution_route_mode.value == "UNIFIED_INTERNAL"
    assert status.safety_runtime.runtime_redaction_active is False
    assert status.safety_governance.governance_ready is False
    assert status.safety_governance.blocking_area_count == 3
    assert status.safety_governance.runbook_readiness.runbook_ready is False
    assert status.resilience_runtime.posture.value == "LOCAL_OR_DEMO_CONTINUITY"
    assert status.resilience_runtime.delivery_stage.value == "DRILL_VERIFIED"
    assert status.resilience_runtime.recovery_state.value == "DEGRADED"
    assert status.resilience_runtime.authoritative_dependency_count >= 8
    assert status.resilience_governance.governance_ready is False
    assert status.resilience_governance.activation_readiness.activation_ready is False
    assert status.resilience_governance.runbook_readiness.runbook_ready is True
    assert status.resilience_governance.drill_evidence.drill_evidence_ready is False
    assert status.production_baseline.posture.value == "LOCAL_OR_DEMO_CAPABLE"
    assert status.production_baseline.production_ready is False
    assert status.production_baseline.prod_shaped_local is False
    assert status.production_go_live.platform_state.value == "TECHNICALLY_RUNNING"
    assert status.production_go_live.use_case_state.value == "PRE_PROD_VALIDATION"
    assert status.production_go_live.platform_production_approved is False
    assert status.production_go_live.use_case_production_approved is False
    assert status.production_go_live.provider_freeze_state.value == "NOT_APPLICABLE"
    assert status.production_go_live.provider_rollback_state.value == "NOT_APPLICABLE"
    assert any(
        domain.domain_id == "managed_object_storage"
        and domain.review_surface == "/platform/artifacts/governance-status"
        for domain in status.production_go_live.approval_domains
    )
    assert status.production_go_live_governance.governance_ready is False
    assert status.production_go_live_governance.activation_readiness.activation_ready is False
    assert status.production_go_live_governance.runbook_readiness.runbook_ready is False
    assert status.production_go_live_governance.use_case_approval.approval_state.value == (
        "PRE_PROD_VALIDATION"
    )
    assert status.production_go_live_governance.use_case_approval.active_production_ready is False
    assert status.production_go_live_governance.go_live_decision == "BLOCKED"
    assert status.production_baseline_governance.governance_ready is False
    assert status.production_baseline_governance.activation_readiness.activation_ready is False
    assert status.production_baseline_governance.runbook_readiness.runbook_ready is True
    assert any(
        dependency["dependency_id"] == "database_backend"
        for dependency in [item.model_dump() for item in status.production_baseline.dependencies]
    )
    assert (
        status.safety_governance.evidence_readiness.approval_gate.domain_id == "safety_enforcement"
    )
    assert status.startup_readiness_blocking is True
    assert status.startup_readiness_warnings == ["audit store: configuration required"]


def test_build_platform_runtime_status_reports_dedicated_async_worker_cutover(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    settings.deployment_split_stage = "unified"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-prod-shaped-local.db'}"
    settings.audit_store_mode = "sqlalchemy"
    settings.prompt_store_mode = "sqlalchemy"
    settings.retrieval_store_mode = "sqlalchemy"
    settings.access_control_store_mode = "sqlalchemy"
    settings.workflow_pack_registry_store_mode = "sqlalchemy"
    settings.provider_operations_store_mode = "sqlalchemy"
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.evaluation_runtime_store_mode = "sqlalchemy"
    settings.artifact_store_mode = "sqlalchemy"
    settings.artifact_object_store_mode = "filesystem"
    settings.artifact_object_store_root = str(tmp_path / "object-store")
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    settings.retrieval_mode = "disabled"
    settings.provider_mode = "disabled"
    upgrade_database_to_head(settings.database_url)
    reset_artifact_store_cache()
    queue = get_test_async_delivery_queue()
    ready_store = StoreRuntimeStatusDescriptor(
        mode="sqlalchemy",
        status=RuntimeReadinessStatus.READY,
        database_configured=True,
        detail="ready",
    )
    monkeypatch.setattr(
        "app.services.async_operational_state.get_async_delivery_queue", lambda: queue
    )
    for target in (
        "get_audit_store_runtime_status",
        "get_prompt_store_runtime_status",
        "get_retrieval_store_runtime_status",
        "get_access_control_store_runtime_status",
        "get_provider_operations_store_runtime_status",
        "get_async_runtime_store_runtime_status",
        "get_evaluation_runtime_store_runtime_status",
        "get_artifact_store_runtime_status",
    ):
        monkeypatch.setattr(
            f"app.services.production_baseline_runtime.{target}",
            lambda: ready_store,
        )

    status = build_platform_runtime_status(None)

    assert status.async_runtime.cutover_state == "dedicated_workers_active"
    assert status.async_runtime.queue_mode == "ACTIVE"
    assert status.async_runtime.queue_backend == "redis_queue"
    assert status.async_runtime.worker_mode == "DEDICATED"
    assert status.async_runtime.active_worker_execution == "queue_backed_workers"
    assert status.async_runtime.queue_backlog_count == 0
    assert status.deployment_split.configured_stage.value == "UNIFIED"
    assert status.deployment_split.effective_stage.value == "UNIFIED"
    assert status.deployment_split_governance.governance_ready is True
    assert status.evaluation_runtime.async_execution_route_mode.value == "UNIFIED_INTERNAL"
    assert status.resilience_runtime.posture.value == "PARTIAL_RUNTIME_DURABILITY"
    assert status.resilience_runtime.delivery_stage.value == "DRILL_VERIFIED"
    assert status.resilience_runtime.recovery_state.value == "DEGRADED"
    assert status.production_baseline.posture.value == "LOCAL_OR_DEMO_CAPABLE"
    assert status.production_baseline.prod_shaped_local is False
    assert status.production_baseline.production_ready is False


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
            caller_app="lotus-platform",
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


def test_build_platform_runtime_status_reflects_artifact_runtime_posture(
    tmp_path: Path,
) -> None:
    settings.artifact_store_mode = "sqlalchemy"
    settings.artifact_object_store_mode = "filesystem"
    settings.artifact_object_store_root = str(tmp_path / "objects")
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-platform-artifacts.db'}"
    upgrade_database_to_head(settings.database_url)
    reset_artifact_store_cache()

    status = build_platform_runtime_status(None)

    assert status.artifact_runtime.metadata_store_mode == "sqlalchemy"
    assert status.artifact_runtime.object_store_mode == "filesystem"
    assert status.artifact_runtime.metadata_store.status.value == "READY"
    assert status.artifact_runtime.object_store.status.value == "READY"
    assert status.artifact_governance.governance_ready is False
