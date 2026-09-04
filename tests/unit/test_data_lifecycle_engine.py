"""The lifecycle engine applies exactly what the policy claims (issue #158, S2a).

Expiry honours age semantics per family (simple age, terminal-state age,
tenant-scoped legal hold), every non-empty deletion writes append-only
evidence with a digest, a second run is a no-op, and DECLARED_ONLY families
are reported untouched - the retention claim is exactly as broad as the
engine's handlers, pinned in both directions.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from app.contracts.access_control import (
    AuthorizationCapabilityType,
    AuthorizationDecision,
    AuthorizationOutcome,
    TenantPolicyMode,
)
from app.contracts.audit import AuditRecordResponse
from app.contracts.audit_access import INTERNAL_AGGREGATE_AUDIT_SCOPE
from app.contracts.data_lifecycle import DataLegalHoldRecord
from app.contracts.evidence import ExecutionEvidenceBundle
from app.contracts.prompts import PromptRolloutRole, PromptSelectionTraceDescriptor
from app.contracts.providers import ProviderAdapterKind
from app.contracts.safety import RedactionPosture
from app.contracts.tasks import OutputLabel, TaskCategory, TaskExecutionStatus
from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeJobRecord,
    AsyncRuntimeLeaseRecord,
)
from app.services.async_runtime_store import get_async_runtime_store
from app.services.audit_store import get_audit_store
from app.services.data_lifecycle_engine import (
    enforced_family_handler_ids,
    run_data_lifecycle,
)
from app.services.data_lifecycle_policy import load_retention_policy
from app.services.safety_runtime import build_safety_execution_outcome_from_record
from app.services.workflow_pack_admission_lease_store import (
    get_workflow_pack_admission_lease_repository,
)
from app.contracts.workflow_pack_queue_policies import (
    WorkflowPackQueueLane,
    WorkflowPackQueueState,
)
from app.services.workflow_pack_queue_admission_models import WorkflowPackQueueAdmissionLease


def _iso(days_ago: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()


def _audit_record(request_id: str, *, tenant_id: str | None, days_ago: int) -> AuditRecordResponse:
    return AuditRecordResponse(
        request_id=request_id,
        execution_status=TaskExecutionStatus.COMPLETED,
        task_id="explain.v1",
        category=TaskCategory.EXPLAIN,
        output_label=OutputLabel.EXPLANATION_ONLY,
        caller_app="lotus-manage",
        correlation_id=f"corr-{request_id}",
        requested_by="ops.user@lotus",
        tenant_id=tenant_id,
        prompt_version="foundation.explain.v1",
        prompt_selection=PromptSelectionTraceDescriptor(
            task_id="explain.v1",
            prompt_version="foundation.explain.v1",
            rollout_role=PromptRolloutRole.ACTIVE,
            selection_reason="test",
            active_prompt_version="foundation.explain.v1",
            candidate_prompt_version=None,
            previous_active_prompt_version=None,
            latest_control_event=None,
        ),
        provider_mode="disabled",
        provider_id="text.stub",
        adapter_kind=ProviderAdapterKind.STUB,
        model_id=None,
        safety_mode="documented_only",
        redaction_posture=RedactionPosture.MINIMIZATION_REQUIRED,
        enforced_safety_controls=["response_labeling"],
        safety_outcome=build_safety_execution_outcome_from_record(
            safety_mode="documented_only",
            output_label=OutputLabel.EXPLANATION_ONLY,
            redaction_posture=RedactionPosture.MINIMIZATION_REQUIRED,
            enforced_controls=["response_labeling"],
        ),
        authorization=AuthorizationDecision(
            caller_app="lotus-manage",
            capability_type=AuthorizationCapabilityType.TASK_EXECUTION,
            outcome=AuthorizationOutcome.ALLOWED,
            allowed=True,
            tenant_policy_mode=TenantPolicyMode.RESTRICTED,
            task_id="explain.v1",
            requested_source_ids=[],
            effective_source_ids=[],
            tenant_id=tenant_id,
            summary="test",
        ),
        generated_at=_iso(days_ago),
        stubbed=True,
        context_summary="s",
        context_keys=[],
        source_refs=[],
        result_preview="p",
        structured_output={},
        evidence=ExecutionEvidenceBundle(descriptors=[]),
    )


def _job(job_id: str, *, status: str, days_ago: int) -> AsyncRuntimeJobRecord:
    return AsyncRuntimeJobRecord(
        job_id=job_id,
        job_type="evaluation_run",
        target_id=None,
        lifecycle_status=status,
        submitted_at=_iso(days_ago),
        caller_app="lotus-platform",
        correlation_id=f"corr-{job_id}",
        payload_summary="snapshot",
        execution_path="queue",
        related_evaluation_run_id=None,
        latest_message="m",
        attempt_count=1,
        artifact_ids=[],
    )


def _seed_expiry_matrix() -> None:
    audit = get_audit_store()
    audit.save(_audit_record("air_old_a", tenant_id="tenant-a", days_ago=2600))
    audit.save(_audit_record("air_old_b_held", tenant_id="tenant-b", days_ago=2600))
    audit.save(_audit_record("air_young_a", tenant_id="tenant-a", days_ago=10))
    audit.place_legal_hold(
        DataLegalHoldRecord(
            hold_id="hold_b",
            family_id="audit_evidence",
            key_type="tenant",
            key_value="tenant-b",
            reason="Litigation hold for tenant-b.",
            placed_by="legal.ops@lotus",
            placed_at=_iso(1),
        )
    )

    jobs = get_async_runtime_store()
    jobs.save_job(_job("job_old_done", status="COMPLETED", days_ago=400))
    jobs.save_attempt(
        AsyncRuntimeAttemptRecord(
            attempt_id="att_old_done",
            job_id="job_old_done",
            attempt_number=1,
            lifecycle_status="COMPLETED",
            worker_id="w1",
            claimed_at=_iso(400),
            heartbeat_at=_iso(400),
            started_at=_iso(400),
            completed_at=_iso(400),
            failure_reason=None,
            recorded_message="done",
        )
    )
    jobs.save_job(_job("job_old_queued", status="QUEUED", days_ago=400))
    jobs.save_job(_job("job_young_done", status="COMPLETED", days_ago=5))
    jobs.save_lease(
        AsyncRuntimeLeaseRecord(
            lease_id="lease_stale",
            job_id="job_old_queued",
            attempt_id="att_x",
            worker_id="w-dead",
            claimed_at=_iso(40),
            heartbeat_at=_iso(40),
            lease_expires_at=_iso(39),
        )
    )

    admission = get_workflow_pack_admission_lease_repository()
    admission.try_admit(
        WorkflowPackQueueAdmissionLease(
            queue_item_id="adm_old",
            policy_id="policy-1",
            workflow_pack_id="pack.v1",
            workflow_pack_version="1",
            lane=WorkflowPackQueueLane.BATCH,
            state=WorkflowPackQueueState.ADMITTED,
            admitted_at=_iso(45),
        ),
        pack_limit=5,
        lane_limit=5,
    )
    admission.try_admit(
        WorkflowPackQueueAdmissionLease(
            queue_item_id="adm_young",
            policy_id="policy-2",
            workflow_pack_id="pack.v1",
            workflow_pack_version="1",
            lane=WorkflowPackQueueLane.BATCH,
            state=WorkflowPackQueueState.ADMITTED,
            admitted_at=_iso(2),
        ),
        pack_limit=5,
        lane_limit=5,
    )


def test_policy_enforced_families_match_engine_handlers_exactly() -> None:
    """The retention claim is exactly as broad as the engine: every ENFORCED
    family has a handler and every handler's family is ENFORCED."""

    policy = load_retention_policy()
    enforced = {f.family_id for f in policy.families if f.enforcement == "ENFORCED"}
    assert enforced == enforced_family_handler_ids()


def test_expiry_honours_age_terminal_state_and_legal_hold() -> None:
    _seed_expiry_matrix()

    report = run_data_lifecycle(actor="test.operator")

    results = {r.family_id: r for r in report.results}
    audit = get_audit_store()
    remaining = {r.request_id for r in audit.list(scope=INTERNAL_AGGREGATE_AUDIT_SCOPE, limit=50)}
    # Past-retention tenant-a row expired; the held tenant-b row and the
    # young row remain.
    assert remaining == {"air_old_b_held", "air_young_a"}
    assert results["audit_evidence"].deleted_count == 1
    assert "1 past-retention rows kept under legal hold" in results["audit_evidence"].detail

    jobs = get_async_runtime_store()
    job_ids = {j.job_id for j in jobs.list_jobs()}
    # The old terminal job went (with its attempt); the old QUEUED job is
    # in-flight truth and stays; the young terminal job stays.
    assert job_ids == {"job_old_queued", "job_young_done"}
    assert results["async_runtime_content"].deleted_count == 1

    # The stale worker lease and the old admission lease expired.
    assert results["transient_operational_leases"].deleted_count == 2
    assert {
        lease.queue_item_id
        for lease in get_workflow_pack_admission_lease_repository().list_leases()
    } == {"adm_young"}

    # Deletion evidence: one event per non-empty family, digest over sorted ids.
    events = {e.family_id: e for e in audit.list_lifecycle_events(limit=20)}
    assert set(events) == {
        "audit_evidence",
        "async_runtime_content",
        "transient_operational_leases",
    }
    assert events["audit_evidence"].row_count == 1
    assert events["audit_evidence"].deleted_ids_digest == hashlib.sha256(b"air_old_a").hexdigest()
    assert events["audit_evidence"].policy_version == report.policy_version
    assert events["audit_evidence"].actor == "test.operator"

    # Non-engine families are reported, never touched: every time-bounded
    # family is now ENFORCED, and the not-time-bounded ones say so.
    assert results["governed_registry_configuration"].enforcement == "NOT_TIME_BOUNDED"
    assert results["governed_registry_configuration"].deleted_count == 0
    assert results["governed_registry_configuration"].event_id is None


def test_second_run_is_idempotent() -> None:
    _seed_expiry_matrix()
    run_data_lifecycle(actor="test.operator")
    events_before = len(get_audit_store().list_lifecycle_events(limit=50))

    second = run_data_lifecycle(actor="test.operator")

    assert all(result.deleted_count == 0 for result in second.results)
    assert len(get_audit_store().list_lifecycle_events(limit=50)) == events_before


def test_unparseable_timestamps_are_never_silently_expired() -> None:
    jobs = get_async_runtime_store()
    record = _job("job_bad_ts", status="COMPLETED", days_ago=400)
    jobs.save_job(AsyncRuntimeJobRecord(**{**record.__dict__, "submitted_at": "not-a-timestamp"}))

    run_data_lifecycle(actor="test.operator")

    assert {j.job_id for j in jobs.list_jobs()} == {"job_bad_ts"}


def test_released_hold_no_longer_protects() -> None:
    audit = get_audit_store()
    audit.save(_audit_record("air_released", tenant_id="tenant-c", days_ago=2600))
    audit.place_legal_hold(
        DataLegalHoldRecord(
            hold_id="hold_c",
            family_id="audit_evidence",
            key_type="tenant",
            key_value="tenant-c",
            reason="Hold pending review.",
            placed_by="legal.ops@lotus",
            placed_at=_iso(2),
        )
    )
    first = run_data_lifecycle(actor="test.operator")
    assert {r.family_id: r.deleted_count for r in first.results}["audit_evidence"] == 0

    assert audit.release_legal_hold(hold_id="hold_c", released_at=_iso(0)) is True
    assert audit.release_legal_hold(hold_id="hold_c", released_at=_iso(0)) is False

    second = run_data_lifecycle(actor="test.operator")
    assert {r.family_id: r.deleted_count for r in second.results}["audit_evidence"] == 1
    assert audit.list(scope=INTERNAL_AGGREGATE_AUDIT_SCOPE, limit=10) == []


def test_sqlalchemy_adapters_round_trip(tmp_path: object, monkeypatch: object) -> None:
    """The durable adapters implement the same lifecycle surface: expiry,
    cascade deletion, hold protection and evidence all survive SQL."""

    from pathlib import Path

    import pytest as _pytest

    from app.config import settings
    from tests.support.migration_runner import upgrade_database_to_head

    assert isinstance(monkeypatch, _pytest.MonkeyPatch)
    assert isinstance(tmp_path, Path)
    database_url = f"sqlite:///{tmp_path / 'lifecycle-s2a.db'}"
    upgrade_database_to_head(database_url)
    monkeypatch.setattr(settings, "database_url", database_url)
    for mode_field in (
        "audit_store_mode",
        "async_runtime_store_mode",
        "workflow_pack_admission_store_mode",
        "kill_switch_store_mode",
        "prompt_store_mode",
        "workflow_pack_registry_store_mode",
        "model_catalogue_store_mode",
        "provider_operations_store_mode",
        "provider_retention_confirmation_store_mode",
        "workflow_pack_run_store_mode",
        "workflow_pack_task_flow_store_mode",
        "workflow_pack_queue_event_store_mode",
        "artifact_store_mode",
        "evaluation_runtime_store_mode",
        "retrieval_store_mode",
    ):
        monkeypatch.setattr(settings, mode_field, "sqlalchemy")

    _seed_expiry_matrix()
    _seed_control_plane_matrix()
    _seed_run_and_eval_matrix()
    report = run_data_lifecycle(actor="test.operator")

    results = {r.family_id: r.deleted_count for r in report.results}
    assert results["audit_evidence"] == 1
    assert results["async_runtime_content"] == 1
    assert results["transient_operational_leases"] == 2
    assert results["control_plane_evidence"] == 11
    assert results["workflow_run_records"] == 4
    assert results["artifact_content"] == 1
    assert results["evaluation_approval_evidence"] == 1
    assert results["evaluation_case_content"] == 1

    # The SQL adapters' empty deletions are safe no-ops.
    from app.provider_retention_confirmations.store import (
        get_provider_retention_confirmation_store,
    )
    from app.services.kill_switch_store import get_kill_switch_repository
    from app.services.model_catalogue_store import get_model_catalogue_repository
    from app.services.prompt_store import get_prompt_repository
    from app.services.provider_operations_store import get_provider_operations_store
    from app.services.workflow_pack_registry_store import get_workflow_pack_registry_store

    assert get_kill_switch_repository().delete_activations([]) == 0
    assert get_prompt_repository().delete_prompt_rollout_events([]) == 0
    assert get_workflow_pack_registry_store().delete_control_events([]) == 0
    assert get_model_catalogue_repository().delete_lifecycle_events([]) == 0
    assert get_model_catalogue_repository().delete_drift_observations([]) == 0
    assert get_provider_operations_store().delete_operations_events([]) == 0
    assert get_provider_operations_store().delete_governed_actions([]) == 0
    assert get_provider_retention_confirmation_store().delete_confirmations([]) == 0
    assert get_audit_store().delete_access_events([]) == 0
    assert get_audit_store().delete_lifecycle_events([]) == 0

    from app.services.artifact_store import get_artifact_repository
    from app.services.evaluation_runtime_store import get_evaluation_runtime_store
    from app.services.workflow_pack_queue_event_store import get_workflow_pack_queue_event_store
    from app.services.workflow_pack_run_store import get_workflow_pack_run_store
    from app.services.workflow_pack_task_flow_store import get_workflow_pack_task_flow_store
    from app.workflow_pack_execution_idempotency.store import (
        get_workflow_pack_execution_idempotency_store,
    )

    assert get_workflow_pack_run_store().delete_runs_with_events([]) == (0, 0)
    assert get_workflow_pack_task_flow_store().delete_task_flows_with_checkpoints([]) == (0, 0)
    assert get_workflow_pack_queue_event_store().delete_events([]) == 0
    assert get_artifact_repository().delete_artifacts([]) == 0
    assert get_workflow_pack_execution_idempotency_store().delete_records([]) == 0
    assert get_evaluation_runtime_store().delete_runs_with_dependents([]) == (0, 0, 0)
    assert get_evaluation_runtime_store().delete_case_results([]) == 0

    from app.services.retrieval_store import get_retrieval_repository

    assert get_retrieval_repository().delete_document_versions([]) == 0
    assert get_retrieval_repository().delete_ingestion_jobs([]) == 0
    assert get_retrieval_repository().delete_document_versions(["ver_never"]) == 0
    assert get_retrieval_repository().delete_ingestion_jobs(["ing_never"]) == 0

    audit = get_audit_store()
    assert {r.request_id for r in audit.list(scope=INTERNAL_AGGREGATE_AUDIT_SCOPE, limit=50)} == {
        "air_old_b_held",
        "air_young_a",
    }
    events = audit.list_lifecycle_events(limit=20)
    assert len(events) == 8
    assert all(len(event.deleted_ids_digest) == 64 for event in events)
    assert {j.job_id for j in get_async_runtime_store().list_jobs()} == {
        "job_old_queued",
        "job_young_done",
    }

    second = run_data_lifecycle(actor="test.operator")
    assert all(result.deleted_count == 0 for result in second.results)
    assert len(get_audit_store().list_lifecycle_events(limit=20)) == 8


def test_naive_timestamps_are_treated_as_utc() -> None:
    """A stored instant without a timezone is compared as UTC, not skipped."""

    jobs = get_async_runtime_store()
    record = _job("job_naive_old", status="COMPLETED", days_ago=400)
    naive = (datetime.now(UTC) - timedelta(days=400)).replace(tzinfo=None).isoformat()
    jobs.save_job(AsyncRuntimeJobRecord(**{**record.__dict__, "submitted_at": naive}))

    report = run_data_lifecycle(actor="test.operator")

    assert {r.family_id: r.deleted_count for r in report.results}["async_runtime_content"] == 1
    assert jobs.list_jobs() == []


def test_repository_edge_paths_are_bounded() -> None:
    """Empty and unknown-id deletions are safe no-ops in both adapters'
    shared semantics: nothing deleted, nothing raised."""

    audit = get_audit_store()
    assert audit.delete_records([]) == 0
    assert audit.delete_records(["air_never_existed"]) == 0

    jobs = get_async_runtime_store()
    assert jobs.delete_job_records([]) == (0, 0, 0)
    assert jobs.delete_job_records(["job_never_existed"]) == (0, 0, 0)


def test_sql_hold_release_and_filters_round_trip(tmp_path: object, monkeypatch: object) -> None:
    """The SQL adapter's hold lifecycle: family filter, release once, refuse
    a second release, and empty deletions."""

    from pathlib import Path

    import pytest as _pytest

    from app.config import settings
    from tests.support.migration_runner import upgrade_database_to_head

    assert isinstance(monkeypatch, _pytest.MonkeyPatch)
    assert isinstance(tmp_path, Path)
    database_url = f"sqlite:///{tmp_path / 'lifecycle-holds.db'}"
    upgrade_database_to_head(database_url)
    monkeypatch.setattr(settings, "database_url", database_url)
    monkeypatch.setattr(settings, "audit_store_mode", "sqlalchemy")

    audit = get_audit_store()
    audit.place_legal_hold(
        DataLegalHoldRecord(
            hold_id="hold_sql",
            family_id="audit_evidence",
            key_type="tenant",
            key_value="tenant-x",
            reason="r",
            placed_by="legal.ops@lotus",
            placed_at=_iso(1),
        )
    )
    assert [h.hold_id for h in audit.list_active_legal_holds(family_id="audit_evidence")] == [
        "hold_sql"
    ]
    assert audit.list_active_legal_holds(family_id="other_family") == []
    assert audit.release_legal_hold(hold_id="hold_sql", released_at=_iso(0)) is True
    assert audit.release_legal_hold(hold_id="hold_sql", released_at=_iso(0)) is False
    assert audit.release_legal_hold(hold_id="hold_missing", released_at=_iso(0)) is False
    assert audit.list_active_legal_holds() == []
    assert audit.delete_records([]) == 0


def _authz() -> AuthorizationDecision:
    return AuthorizationDecision(
        caller_app="lotus-platform",
        capability_type=AuthorizationCapabilityType.PROVIDER_CONTROL,
        outcome=AuthorizationOutcome.ALLOWED,
        allowed=True,
        tenant_policy_mode=TenantPolicyMode.OPTIONAL,
        task_id=None,
        requested_source_ids=[],
        effective_source_ids=[],
        tenant_id=None,
        summary="test",
    )


def _seed_control_plane_matrix() -> None:
    from app.contracts.audit_access import (
        AuditAccessEvent,
        AuditAccessOperation,
        AuditAccessOutcome,
        AuditReadScopeMode,
    )
    from app.contracts.governed_actions import (
        GovernedActionRecord,
        GovernedActionStatus,
        GovernedActionType,
        GovernedActorClass,
    )
    from app.contracts.kill_switches import (
        KillSwitchActivationRecord,
        KillSwitchScope,
        KillSwitchSemantics,
    )
    from app.contracts.model_catalogue import (
        ModelLifecycleState,
        ModelLifecycleTransitionRecord,
        ModelRevisionDriftObservation,
    )
    from app.contracts.prompts import PromptControlActionType
    from app.contracts.workflow_packs import (
        WorkflowPackActivationState,
        WorkflowPackControlActionType,
        WorkflowPackControlEventDescriptor,
        WorkflowPackRegistrationStatus,
    )
    from app.repositories.async_runtime_repository import AsyncRuntimeControlEventRecord
    from app.repositories.provider_operations_repository import ProviderOperationsEventRecord
    from app.services.kill_switch_store import get_kill_switch_repository
    from app.services.model_catalogue_store import get_model_catalogue_repository
    from app.services.prompt_store import get_prompt_repository
    from app.services.prompt_rollout_models import PromptRolloutEventRecord
    from app.services.provider_operations_store import get_provider_operations_store
    from app.services.workflow_pack_registry_store import get_workflow_pack_registry_store

    audit = get_audit_store()
    for event_id, age in (("aae_old", 2600), ("aae_young", 10)):
        audit.save_access_event(
            AuditAccessEvent(
                event_id=event_id,
                caller_app="lotus-platform",
                caller_trust_source="verified_service_jwt",
                scope_mode=AuditReadScopeMode.ALL_TENANTS,
                operation=AuditAccessOperation.LIST_RECORDS,
                outcome=AuditAccessOutcome.SUCCEEDED,
                returned_record_count=1,
                recorded_at=_iso(age),
            )
        )

    ops = get_provider_operations_store()
    from app.contracts.provider_operations import ProviderOperationsControlActionType

    for event_id, age in (("poe_old", 2600), ("poe_young", 10)):
        ops.save_operations_event(
            ProviderOperationsEventRecord(
                event_id=event_id,
                action_type=ProviderOperationsControlActionType.RESET_DEGRADATION,
                scope=None,
                scope_key=None,
                reason="r",
                requested_by="ops",
                approved_by="ops2",
                affected_record_count=1,
                authorization=_authz(),
                recorded_at=_iso(age),
            )
        )

    from app.repositories.provider_operations_repository import ProviderAttemptDebitRecord

    for debit_id, age in (("adbt_old", 2600), ("adbt_young", 10)):
        ops.record_attempt_debit(
            ProviderAttemptDebitRecord(
                debit_id=debit_id,
                provider_id="text.openai",
                basis="ACTUAL_USAGE",
                amount_usd=0.001,
                input_tokens=10,
                output_tokens=10,
                rate_card_ref="default-live-text",
                recorded_at=_iso(age),
            ),
            budget_key="live_text_generation",
        )

    def _gact(action_id: str, status: "GovernedActionStatus", age: int) -> None:
        ops.upsert_governed_action(
            GovernedActionRecord(
                action_id=action_id,
                action_type=GovernedActionType.KILL_SWITCH_CLEAR,
                actor_class=GovernedActorClass.HUMAN_APPROVED,
                status=status,
                target="ksw_x",
                action_hash="a" * 64,
                action_payload={"k": "v"},
                requester_caller_app="lotus-platform",
                requester_trust_source="verified_service_jwt",
                requester_key_id="k1",
                requested_at=_iso(age),
            )
        )

    _gact("gact_old_executed", GovernedActionStatus.EXECUTED, 2600)
    _gact("gact_old_pending", GovernedActionStatus.PENDING, 2600)
    _gact("gact_young", GovernedActionStatus.EXECUTED, 10)

    prompts = get_prompt_repository()
    from app.contracts.prompts import PromptRolloutSelectionMode
    from app.services.prompt_rollout_models import PromptRolloutStateRecord

    for event_id, age in (("pre_old", 2600), ("pre_young", 10)):
        prompts.save_prompt_rollout_transition(
            rollout_state=PromptRolloutStateRecord(
                task_id="explain.v1",
                active_prompt_version="foundation.explain.v1",
                candidate_prompt_version=None,
                previous_active_prompt_version=None,
                rollout_mode=PromptRolloutSelectionMode.GOVERNED_STATE_READ_ONLY,
                runtime_mutation_enabled=False,
            ),
            updated_prompts=[],
            event=PromptRolloutEventRecord(
                event_id=event_id,
                task_id="explain.v1",
                action_type=PromptControlActionType.ROLLBACK_TO_PREVIOUS_ACTIVE,
                requested_by="lotus-platform (credential k1)",
                approved_by=None,
                reason="r",
                prior_active_prompt_version=None,
                resulting_active_prompt_version=None,
                prior_candidate_prompt_version=None,
                resulting_candidate_prompt_version=None,
                authorization=_authz(),
                recorded_at=_iso(age),
            ),
        )

    async_runtime = get_async_runtime_store()
    for event_id, age in (("ace_old", 2600), ("ace_young", 10)):
        async_runtime.save_control_event(
            AsyncRuntimeControlEventRecord(
                event_id=event_id,
                job_id="job_x",
                action_type="QUARANTINE_QUEUED_JOB",
                requested_by="worker-1",
                approved_by=None,
                reason="r",
                prior_status="QUEUED",
                resulting_status="ABANDONED",
                affected_attempt_id=None,
                authorization=_authz(),
                recorded_at=_iso(age),
            )
        )

    switches = get_kill_switch_repository()

    def _switch(switch_id: str, age: int, cleared: bool) -> None:
        switches.upsert_activation(
            KillSwitchActivationRecord(
                switch_id=switch_id,
                scope=KillSwitchScope.PROVIDER,
                semantics=KillSwitchSemantics.HARD_KILL,
                target="text.openai",
                reason="r",
                requested_by="lotus-platform (credential k1)",
                approved_by=None,
                activated_at=_iso(age),
                cleared_at=_iso(age - 1) if cleared else None,
                cleared_by="lotus-platform (credential k2)" if cleared else None,
                clear_reason="resolved" if cleared else None,
            )
        )

    _switch("ksw_old_cleared", 2600, cleared=True)
    _switch("ksw_old_enforcing", 2600, cleared=False)
    _switch("ksw_young_cleared", 10, cleared=True)

    registry = get_workflow_pack_registry_store()
    for event_id, age in (("wpe_old", 2600), ("wpe_young", 10)):
        registry.save_control_event(
            WorkflowPackControlEventDescriptor(
                event_id=event_id,
                pack_id="advisor_brief.pack",
                version="v1",
                action_type=WorkflowPackControlActionType.PAUSE,
                requested_by="ops.user@lotus",
                approved_by="ops.approver@lotus",
                reason="r",
                prior_registration_status=WorkflowPackRegistrationStatus.REGISTERED,
                resulting_registration_status=WorkflowPackRegistrationStatus.REGISTERED,
                prior_activation_state=WorkflowPackActivationState.ACTIVE,
                resulting_activation_state=WorkflowPackActivationState.PAUSED,
                caller_app="lotus-platform",
                authorization=_authz(),
                recorded_at=_iso(age),
            )
        )

    catalogue = get_model_catalogue_repository()
    for event_id, age in (("mlc_old", 2600), ("mlc_young", 10)):
        catalogue.append_lifecycle_event(
            ModelLifecycleTransitionRecord(
                event_id=event_id,
                entry_id="text.openai:gpt-5.4",
                from_state=ModelLifecycleState.CATALOGUED,
                to_state=ModelLifecycleState.EVALUATING,
                reason="r",
                requested_by="lotus-platform (credential k1)",
                approved_by=None,
                recorded_at=_iso(age),
            )
        )

    def _drift(observation_id: str, last_age: int) -> None:
        catalogue.upsert_drift_observation(
            ModelRevisionDriftObservation(
                observation_id=observation_id,
                entry_id="text.openai:gpt-5.4",
                expected_identity="gpt-5.4",
                observed_model_id="gpt-5.4-other",
                revision_pinned_at_observation=False,
                first_observed_at=_iso(2600),
                last_observed_at=_iso(last_age),
                observation_count=3,
            )
        )

    _drift("drift_old", 2600)
    _drift("drift_recent", 5)

    from app.provider_retention_confirmations.repository import (
        ProviderRetentionConfirmationRecord,
    )
    from app.provider_retention_confirmations.store import (
        get_provider_retention_confirmation_store,
    )
    from tests.unit.test_provider_retention_confirmation import BASE_RUN, _issue, _request

    confirmations = get_provider_retention_confirmation_store()
    for suffix, age in (("old", 2600), ("young", 10)):
        envelope = _issue(BASE_RUN, _request())
        aged = envelope.model_copy(
            update={
                "claims": envelope.claims.model_copy(
                    update={
                        "confirmation_id": f"conf_{suffix}",
                        "provider_confirmation_ref": f"provider-confirmation-{suffix}",
                        "issued_at_utc": _iso(age),
                    }
                )
            }
        )
        confirmations.save(
            ProviderRetentionConfirmationRecord(
                idempotency_key=f"idem-{suffix}",
                request_fingerprint="f" * 64,
                envelope=aged,
            )
        )


def test_control_plane_evidence_expiry_honours_the_protective_predicates() -> None:
    """Old evidence expires across every table in the family; an ENFORCING
    kill switch, a PENDING governed action, and a recently-observed drift
    are never expired - and the single family event's digest covers the
    table-prefixed ids."""

    from app.services.kill_switch_store import get_kill_switch_repository
    from app.services.model_catalogue_store import get_model_catalogue_repository
    from app.services.provider_operations_store import get_provider_operations_store

    _seed_control_plane_matrix()

    report = run_data_lifecycle(actor="test.operator")

    results = {r.family_id: r for r in report.results}
    control = results["control_plane_evidence"]
    # aae_old, poe_old, adbt_old, gact_old_executed, pre_old, ace_old,
    # ksw_old_cleared, wpe_old, mlc_old, drift_old, conf_old = 11 expired rows.
    assert control.deleted_count == 11
    assert "never expired" in control.detail

    ops = get_provider_operations_store()
    remaining_actions = {
        a.action_id for a in ops.list_governed_actions(status=None, target=None, limit=50)
    }
    assert remaining_actions == {"gact_old_pending", "gact_young"}

    switches = {s.switch_id for s in get_kill_switch_repository().list_activations()}
    assert switches == {"ksw_old_enforcing", "ksw_young_cleared"}

    catalogue = get_model_catalogue_repository()
    assert {o.observation_id for o in catalogue.list_all_drift_observations(limit=10)} == {
        "drift_recent"
    }
    assert {e.event_id for e in catalogue.list_all_lifecycle_events(limit=10)} == {"mlc_young"}

    audit = get_audit_store()
    events = {e.family_id: e for e in audit.list_lifecycle_events(limit=20)}
    control_event = events["control_plane_evidence"]
    assert control_event.row_count == 11
    expected_ids = sorted(
        [
            "audit_access_events:aae_old",
            "provider_operations_events:poe_old",
            "provider_attempt_debits:adbt_old",
            "provider_governed_actions:gact_old_executed",
            "prompt_rollout_events:pre_old",
            "async_control_events:ace_old",
            "kill_switch_activations:ksw_old_cleared",
            "workflow_pack_control_events:wpe_old",
            "model_catalogue_lifecycle_events:mlc_old",
            "model_revision_drift_observations:drift_old",
            "provider_retention_confirmations:conf_old",
        ]
    )
    assert (
        control_event.deleted_ids_digest
        == hashlib.sha256("\n".join(expected_ids).encode("utf-8")).hexdigest()
    )

    second = run_data_lifecycle(actor="test.operator")
    assert all(result.deleted_count == 0 for result in second.results)


def _seed_run_and_eval_matrix() -> None:
    from app.contracts.artifacts import ArtifactLifecycleStatus, ArtifactStorageBackend
    from app.repositories.artifact_repository import ArtifactRecord
    from app.repositories.evaluation_runtime_repository import (
        EvaluationCaseResultRecord,
        EvaluationRunAttemptRecord,
        EvaluationRunRecord,
    )
    from app.services.artifact_store import get_artifact_repository
    from app.services.evaluation_runtime_store import get_evaluation_runtime_store
    from app.services.workflow_pack_queue_event_store import get_workflow_pack_queue_event_store
    from app.services.workflow_pack_run_store import get_workflow_pack_run_store
    from app.services.workflow_pack_task_flow_store import get_workflow_pack_task_flow_store
    from app.repositories.workflow_pack_task_flow_repository import (
        WorkflowPackTaskFlowCheckpointRecord,
        WorkflowPackTaskFlowRecord,
    )
    from app.repositories.workflow_pack_queue_event_repository import (
        WorkflowPackQueueEventRecord,
    )
    from app.workflow_pack_execution_idempotency.repository import (
        WorkflowPackExecutionIdempotencyRecord,
        WorkflowPackExecutionIdempotencyState,
    )
    from app.workflow_pack_execution_idempotency.store import (
        get_workflow_pack_execution_idempotency_store,
    )
    from tests.support.workflow_pack_task_flow_fixtures import (
        workflow_pack_task_flow_checkpoint,
        workflow_pack_task_flow_descriptor,
    )
    from tests.unit.test_workflow_pack_queue_event_store import _queue_event
    from tests.unit.test_workflow_pack_run_store import _workflow_pack_run_record

    audit = get_audit_store()
    audit.place_legal_hold(
        DataLegalHoldRecord(
            hold_id="hold_run_b",
            family_id="workflow_run_records",
            key_type="tenant",
            key_value="tenant-b",
            reason="Litigation hold for tenant-b run records.",
            placed_by="legal.ops@lotus",
            placed_at=_iso(1),
        )
    )

    runs = get_workflow_pack_run_store()
    runs.save_run(
        _workflow_pack_run_record(run_id="run_old_a", tenant_id="tenant-a", created_at=_iso(2600))
    )
    runs.save_run(
        _workflow_pack_run_record(
            run_id="run_old_b_held", tenant_id="tenant-b", created_at=_iso(2600)
        )
    )
    runs.save_run(
        _workflow_pack_run_record(run_id="run_young_a", tenant_id="tenant-a", created_at=_iso(5))
    )

    flows = get_workflow_pack_task_flow_store()
    old_flow = workflow_pack_task_flow_descriptor(task_flow_id="flow_old")
    old_flow = old_flow.model_copy(update={"created_at": _iso(2600), "tenant_id": "tenant-a"})
    young_flow = workflow_pack_task_flow_descriptor(task_flow_id="flow_young")
    young_flow = young_flow.model_copy(update={"created_at": _iso(3), "tenant_id": "tenant-a"})
    flows.save_task_flow(WorkflowPackTaskFlowRecord(descriptor=old_flow))
    flows.save_task_flow(WorkflowPackTaskFlowRecord(descriptor=young_flow))
    checkpoint = workflow_pack_task_flow_checkpoint(task_flow_id="flow_old")
    flows.save_checkpoint(WorkflowPackTaskFlowCheckpointRecord(descriptor=checkpoint))

    queue_events = get_workflow_pack_queue_event_store()
    old_event = _queue_event("qev_old", "queue-item-1")
    old_event = WorkflowPackQueueEventRecord(
        descriptor=old_event.descriptor.model_copy(update={"recorded_at": _iso(2600)})
    )
    queue_events.save_event(old_event)
    queue_events.save_event(_queue_event("qev_young", "queue-item-2"))

    idempotency = get_workflow_pack_execution_idempotency_store()
    for record_id, age in (("idem_old", 2600), ("idem_young", 4)):
        idempotency.reserve(
            WorkflowPackExecutionIdempotencyRecord(
                record_id=record_id,
                caller_app="lotus-gateway",
                tenant_scope="tenant-a",
                idempotency_key=f"key-{record_id}",
                request_fingerprint="f" * 64,
                state=WorkflowPackExecutionIdempotencyState.COMPLETED,
                owner_token="tok",
                response_payload=None,
                response_checksum_sha256=None,
                failure_code=None,
                created_at=_iso(age),
                updated_at=_iso(age),
            )
        )

    artifacts = get_artifact_repository()

    def _artifact(artifact_id: str, age: int, posture: str) -> None:
        artifacts.save_artifact(
            ArtifactRecord(
                artifact_id=artifact_id,
                domain="workflow_pack_runs",
                artifact_type="advisor_brief_document",
                source_object_kind="workflow_pack_run",
                source_object_id="run_old_a",
                lifecycle_status=ArtifactLifecycleStatus.RUNTIME_GENERATED,
                retention_posture=posture,
                media_type="application/json",
                byte_size=10,
                checksum_sha256="c" * 64,
                storage_backend=ArtifactStorageBackend.MEMORY,
                storage_reference=f"mem://{artifact_id}",
                lineage_parent_artifact_id=None,
                superseded_by_artifact_id=None,
                created_at=_iso(age),
                created_by="lotus-ai",
            )
        )

    _artifact("art_old", 2600, "active")
    _artifact("art_old_review", 2600, "retained_for_review")
    _artifact("art_young", 3, "active")

    evaluation = get_evaluation_runtime_store()
    for run_id, age in (("eval_old", 2600), ("eval_young", 6)):
        evaluation.save_run(
            EvaluationRunRecord(
                run_id=run_id,
                fixture_id="fixture",
                manifest_version="foundation.v1",
                lifecycle_status="COMPLETED",
                triggered_by="operator-a",
                submitted_at=_iso(age),
                async_job_id=None,
                latest_message="m",
                verdict="PASS",
                case_count=1,
            )
        )
        evaluation.save_attempt(
            EvaluationRunAttemptRecord(
                attempt_id=f"att_{run_id}",
                run_id=run_id,
                attempt_number=1,
                lifecycle_status="COMPLETED",
                started_at=_iso(age),
                completed_at=_iso(age),
                worker_id=None,
                latest_message="m",
                verdict="PASS",
                failure_reason=None,
            )
        )
    for case_id, run_id, age in (
        ("case_old", "eval_young", 400),
        ("case_young", "eval_young", 6),
    ):
        evaluation.save_case_result(
            EvaluationCaseResultRecord(
                case_result_id=case_id,
                run_id=run_id,
                attempt_id=f"att_{run_id}",
                case_id=f"c-{case_id}",
                fixture_id="fixture",
                outcome="PASS",
                summary="s",
                evidence_refs=[],
                artifact_ids=[],
                provider_config_sha256=None,
                recorded_at=_iso(age),
            )
        )


def test_run_records_eval_and_artifact_expiry_honour_their_semantics() -> None:
    """S2c: business run records expire under tenant holds with cascading
    children; artifacts retained for review never expire; eval runs cascade
    dependents while young case content ages independently."""

    from app.services.artifact_store import get_artifact_repository
    from app.services.evaluation_runtime_store import get_evaluation_runtime_store
    from app.services.workflow_pack_run_store import get_workflow_pack_run_store
    from app.services.workflow_pack_task_flow_store import get_workflow_pack_task_flow_store
    from app.workflow_pack_execution_idempotency.store import (
        get_workflow_pack_execution_idempotency_store,
    )

    _seed_run_and_eval_matrix()

    report = run_data_lifecycle(actor="test.operator")
    results = {r.family_id: r for r in report.results}

    assert results["workflow_run_records"].deleted_count == 4  # run, flow, qev, idem
    assert "held tenants" in results["workflow_run_records"].detail
    assert {r.run_id for r in get_workflow_pack_run_store().list_runs()} == {
        "run_old_b_held",
        "run_young_a",
    }
    flows = get_workflow_pack_task_flow_store()
    assert {f.descriptor.task_flow_id for f in flows.list_task_flows()} == {"flow_young"}
    assert flows.list_checkpoints(task_flow_id="flow_old") == []
    assert {
        r.record_id for r in get_workflow_pack_execution_idempotency_store().list_records(limit=10)
    } == {"idem_young"}

    assert results["artifact_content"].deleted_count == 1
    assert "retained_for_review" in results["artifact_content"].detail
    assert {a.artifact_id for a in get_artifact_repository().list_artifacts()} == {
        "art_old_review",
        "art_young",
    }

    evaluation = get_evaluation_runtime_store()
    assert results["evaluation_approval_evidence"].deleted_count == 1
    assert {r.run_id for r in evaluation.list_runs()} == {"eval_young"}
    assert evaluation.list_attempts(run_id="eval_old") == []
    assert results["evaluation_case_content"].deleted_count == 1
    assert {c.case_result_id for c in evaluation.list_all_case_results(limit=10)} == {"case_young"}

    events = {e.family_id: e for e in get_audit_store().list_lifecycle_events(limit=20)}
    assert events["workflow_run_records"].row_count == 4
    assert events["evaluation_approval_evidence"].row_count == 1

    second = run_data_lifecycle(actor="test.operator")
    assert all(result.deleted_count == 0 for result in second.results)


def test_passing_case_content_expires_at_the_minimised_horizon() -> None:
    """S4 minimisation: a passing case's content ages out at the declared
    minimised horizon while a same-age failure keeps the full period for
    defect forensics; failures still expire at the family horizon."""

    from app.repositories.evaluation_runtime_repository import (
        EvaluationCaseResultRecord,
        EvaluationRunAttemptRecord,
        EvaluationRunRecord,
    )
    from app.services.evaluation_runtime_store import get_evaluation_runtime_store

    evaluation = get_evaluation_runtime_store()
    evaluation.save_run(
        EvaluationRunRecord(
            run_id="eval_min",
            fixture_id="fixture",
            manifest_version="foundation.v1",
            lifecycle_status="COMPLETED",
            triggered_by="operator-a",
            submitted_at=_iso(5),
            async_job_id=None,
            latest_message="m",
            verdict="PASS",
            case_count=4,
        )
    )
    evaluation.save_attempt(
        EvaluationRunAttemptRecord(
            attempt_id="att_eval_min",
            run_id="eval_min",
            attempt_number=1,
            lifecycle_status="COMPLETED",
            started_at=_iso(5),
            completed_at=_iso(5),
            worker_id=None,
            latest_message="m",
            verdict="PASS",
            failure_reason=None,
        )
    )
    for case_id, outcome, age in (
        ("case_pass_aged", "PASS", 100),
        ("case_fail_aged", "FAIL", 100),
        ("case_pass_fresh", "PASS", 50),
        ("case_fail_expired", "FAIL", 400),
    ):
        evaluation.save_case_result(
            EvaluationCaseResultRecord(
                case_result_id=case_id,
                run_id="eval_min",
                attempt_id="att_eval_min",
                case_id=f"c-{case_id}",
                fixture_id="fixture",
                outcome=outcome,
                summary="s",
                evidence_refs=[],
                artifact_ids=[],
                provider_config_sha256=None,
                recorded_at=_iso(age),
            )
        )

    report = run_data_lifecycle(actor="test.operator")
    results = {r.family_id: r for r in report.results}

    assert results["evaluation_case_content"].deleted_count == 2
    assert "(1 passing cases at the minimised horizon)" in results["evaluation_case_content"].detail
    assert {c.case_result_id for c in evaluation.list_all_case_results(limit=10)} == {
        "case_fail_aged",
        "case_pass_fresh",
    }

    second = run_data_lifecycle(actor="test.operator")
    assert all(result.deleted_count == 0 for result in second.results)


def test_minimising_handlers_and_policy_declarations_agree() -> None:
    """A declared minimised horizon without a handler honouring it would be a
    policy claim the engine does not keep - and a minimising handler for an
    undeclared family would delete ahead of the policy."""

    from app.services.data_lifecycle_engine import MINIMISING_FAMILY_HANDLER_IDS

    declared = {
        family.family_id
        for family in load_retention_policy().families
        if family.minimised_retention_days is not None
    }
    assert declared == MINIMISING_FAMILY_HANDLER_IDS


def test_retrieval_history_expiry_never_touches_current_versions() -> None:
    """S2d: only SUPERSEDED versions age out - the current version of a
    document is live reference state whatever its age - and ingestion-job
    records age with the history."""

    from app.contracts.retrieval import (
        RetrievalDocumentVersionDescriptor,
        RetrievalDocumentVersionLifecycleStatus,
        RetrievalIngestionAction,
        RetrievalIngestionJobDescriptor,
        RetrievalIngestionJobStatus,
    )
    from app.services.retrieval_store import get_retrieval_repository

    repository = get_retrieval_repository()

    def _version(version_id: str, status: str, age: int) -> None:
        repository.save_document_version(
            RetrievalDocumentVersionDescriptor(
                version_id=version_id,
                document_id="doc-1",
                source_id="lotus-platform-rfcs",
                title="t",
                location="loc",
                lifecycle_status=RetrievalDocumentVersionLifecycleStatus(status),
                refresh_action=RetrievalIngestionAction.REFRESH,
                created_at=_iso(age),
                created_by="ops",
                notes="n",
            )
        )

    _version("ver_old_superseded", "SUPERSEDED", 1200)
    _version("ver_old_active", "ACTIVE", 1200)
    _version("ver_young_superseded", "SUPERSEDED", 30)

    for job_id, age in (("ing_old", 1200), ("ing_young", 30)):
        repository.save_ingestion_job(
            RetrievalIngestionJobDescriptor(
                job_id=job_id,
                source_id="lotus-platform-rfcs",
                requested_action=RetrievalIngestionAction.REFRESH,
                status=RetrievalIngestionJobStatus.COMPLETED,
                requested_by="ops",
                requested_at=_iso(age),
                message="m",
            )
        )

    report = run_data_lifecycle(actor="test.operator")
    result = {r.family_id: r for r in report.results}["retrieval_shared_reference"]

    assert result.deleted_count == 2
    assert "never expired" in result.detail
    remaining_versions = {v.version_id for v in repository.list_document_versions()}
    # The memory adapter pre-seeds reference versions; assert on the delta.
    assert "ver_old_superseded" not in remaining_versions
    assert {"ver_old_active", "ver_young_superseded"} <= remaining_versions
    remaining_jobs = {j.job_id for j in repository.list_ingestion_jobs()}
    assert "ing_old" not in remaining_jobs
    assert "ing_young" in remaining_jobs

    second = run_data_lifecycle(actor="test.operator")
    assert all(r.deleted_count == 0 for r in second.results)
