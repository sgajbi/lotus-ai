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

    # DECLARED_ONLY families are reported, never touched.
    assert results["workflow_run_records"].enforcement == "DECLARED_ONLY"
    assert results["workflow_run_records"].deleted_count == 0
    assert results["workflow_run_records"].event_id is None


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
    monkeypatch.setattr(settings, "audit_store_mode", "sqlalchemy")
    monkeypatch.setattr(settings, "async_runtime_store_mode", "sqlalchemy")
    monkeypatch.setattr(settings, "workflow_pack_admission_store_mode", "sqlalchemy")

    _seed_expiry_matrix()
    report = run_data_lifecycle(actor="test.operator")

    results = {r.family_id: r.deleted_count for r in report.results}
    assert results["audit_evidence"] == 1
    assert results["async_runtime_content"] == 1
    assert results["transient_operational_leases"] == 2

    audit = get_audit_store()
    assert {r.request_id for r in audit.list(scope=INTERNAL_AGGREGATE_AUDIT_SCOPE, limit=50)} == {
        "air_old_b_held",
        "air_young_a",
    }
    events = audit.list_lifecycle_events(limit=10)
    assert len(events) == 3
    assert all(len(event.deleted_ids_digest) == 64 for event in events)
    assert {j.job_id for j in get_async_runtime_store().list_jobs()} == {
        "job_old_queued",
        "job_young_done",
    }

    second = run_data_lifecycle(actor="test.operator")
    assert all(result.deleted_count == 0 for result in second.results)
    assert len(get_audit_store().list_lifecycle_events(limit=10)) == 3


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
