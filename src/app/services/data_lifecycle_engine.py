"""The data-lifecycle engine (issue #158, S2a).

One idempotent run applies the retention policy to every family whose
enforcement posture is ENFORCED, honours active legal holds, and writes one
append-only ``data_lifecycle_events`` row per family batch - deletion
evidence without the content. Families marked DECLARED_ONLY are reported,
never touched: the retention claim is exactly as broad as the handlers here.

Handlers are deliberately per-family code rather than a generic column DSL:
each family's semantics (simple age, terminal-state age, tenant-scoped legal
hold) are stated and tested individually, and a test pins that the handler
set and the policy's ENFORCED families agree in both directions.

Timestamps are parsed, never compared as strings: stored ISO instants mix
``+00:00`` and ``Z`` suffixes, and lexicographic comparison across those
formats is wrong.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.contracts.data_lifecycle import DataLifecycleAction, DataLifecycleEventRecord
from app.contracts.audit_access import INTERNAL_AGGREGATE_AUDIT_SCOPE
from app.services.audit_store import get_audit_store
from app.services.async_runtime_store import get_async_runtime_store
from app.services.data_lifecycle_policy import RetentionFamily, load_retention_policy
from app.services.kill_switch_store import get_kill_switch_repository
from app.services.model_catalogue_store import get_model_catalogue_repository
from app.services.prompt_store import get_prompt_repository
from app.services.provider_operations_store import get_provider_operations_store
from app.services.workflow_pack_registry_store import get_workflow_pack_registry_store
from app.provider_retention_confirmations.store import (
    get_provider_retention_confirmation_store,
)
from app.services.artifact_store import get_artifact_repository
from app.services.evaluation_runtime_store import get_evaluation_runtime_store
from app.services.workflow_pack_run_store import get_workflow_pack_run_store
from app.services.workflow_pack_task_flow_store import get_workflow_pack_task_flow_store
from app.services.workflow_pack_queue_event_store import get_workflow_pack_queue_event_store
from app.workflow_pack_execution_idempotency.store import (
    get_workflow_pack_execution_idempotency_store,
)
from app.services.retrieval_store import get_retrieval_repository
from app.services.workflow_pack_admission_lease_store import (
    get_workflow_pack_admission_lease_repository,
)

# The async job states the engine may expire: an in-flight job is runtime
# truth, not an ageing snapshot.
_TERMINAL_JOB_STATUSES = frozenset({"COMPLETED", "FAILED", "ABANDONED", "SUPERSEDED"})

_CANDIDATE_BATCH_LIMIT = 5000


@dataclass(frozen=True)
class FamilyRunResult:
    family_id: str
    enforcement: str
    deleted_count: int
    event_id: str | None
    detail: str


@dataclass(frozen=True)
class DataLifecycleRunReport:
    policy_version: str
    actor: str
    started_at: str
    results: list[FamilyRunResult]


def run_data_lifecycle(*, actor: str) -> DataLifecycleRunReport:
    """Apply retention to every ENFORCED family, evidencing each deletion.

    Idempotent: a second run over the same data deletes nothing and writes no
    further events (events are written only for non-empty batches).
    """

    policy = load_retention_policy()
    now = datetime.now(UTC)
    results: list[FamilyRunResult] = []
    for family in policy.families:
        if family.enforcement != "ENFORCED":
            results.append(
                FamilyRunResult(
                    family_id=family.family_id,
                    enforcement=family.enforcement,
                    deleted_count=0,
                    event_id=None,
                    detail="not applied by the engine; posture is honest about that",
                )
            )
            continue
        handler = _ENFORCED_FAMILY_HANDLERS[family.family_id]
        assert family.retention_days is not None  # ENFORCED implies time-bounded
        cutoff = now - timedelta(days=family.retention_days)
        deleted_ids, detail = handler(family, cutoff)
        event_id: str | None = None
        if deleted_ids:
            event_id = _record_deletion_evidence(
                family=family,
                policy_version=policy.policy_version,
                actor=actor,
                deleted_ids=deleted_ids,
                now=now,
            )
        results.append(
            FamilyRunResult(
                family_id=family.family_id,
                enforcement=family.enforcement,
                deleted_count=len(deleted_ids),
                event_id=event_id,
                detail=detail,
            )
        )
    return DataLifecycleRunReport(
        policy_version=policy.policy_version,
        actor=actor,
        started_at=now.isoformat(),
        results=results,
    )


def _expire_audit_evidence(family: RetentionFamily, cutoff: datetime) -> tuple[list[str], str]:
    """Audit records past retention, honouring tenant-scoped legal holds."""

    repository = get_audit_store()
    held_tenants = {
        hold.key_value
        for hold in repository.list_active_legal_holds(family_id=family.family_id)
        if hold.key_type == "tenant"
    }
    candidates = repository.list(scope=INTERNAL_AGGREGATE_AUDIT_SCOPE, limit=_CANDIDATE_BATCH_LIMIT)
    expired: list[str] = []
    held_count = 0
    for record in candidates:
        if not _is_before(record.generated_at, cutoff):
            continue
        if record.tenant_id is not None and record.tenant_id in held_tenants:
            held_count += 1
            continue
        expired.append(record.request_id)
    deleted = repository.delete_records(expired) if expired else 0
    return expired, (
        f"expired {deleted} audit records; {held_count} past-retention rows kept under legal hold"
    )


def _expire_async_runtime_content(
    family: RetentionFamily, cutoff: datetime
) -> tuple[list[str], str]:
    """Terminal async jobs past retention, with their attempts and leases."""

    repository = get_async_runtime_store()
    expired_job_ids = [
        job.job_id
        for job in repository.list_jobs()
        if job.lifecycle_status in _TERMINAL_JOB_STATUSES and _is_before(job.submitted_at, cutoff)
    ]
    jobs, attempts, leases = (
        repository.delete_job_records(expired_job_ids) if expired_job_ids else (0, 0, 0)
    )
    return expired_job_ids, (
        f"expired {jobs} terminal jobs with {attempts} attempts and {leases} leases; "
        "in-flight jobs are never expired"
    )


def _expire_transient_leases(family: RetentionFamily, cutoff: datetime) -> tuple[list[str], str]:
    """Aged worker and admission leases: coordination state, no client content."""

    async_repository = get_async_runtime_store()
    deleted_ids: list[str] = []
    for lease in async_repository.list_leases():
        if _is_before(lease.claimed_at, cutoff):
            if async_repository.delete_lease(lease_id=lease.lease_id):
                deleted_ids.append(lease.lease_id)
    admission_repository = get_workflow_pack_admission_lease_repository()
    admission_deleted = 0
    for admission_lease in admission_repository.list_leases():
        if _is_before(admission_lease.admitted_at, cutoff):
            if admission_repository.delete_lease(admission_lease.queue_item_id):
                deleted_ids.append(admission_lease.queue_item_id)
                admission_deleted += 1
    return deleted_ids, (
        f"expired {len(deleted_ids) - admission_deleted} worker leases and "
        f"{admission_deleted} admission leases"
    )


def _expire_control_plane_evidence(
    family: RetentionFamily, cutoff: datetime
) -> tuple[list[str], str]:
    """Control-plane evidence past retention, with three protective predicates.

    An ENFORCING kill switch is current control state, never expired; a
    PENDING governed action is a live approval intent, never expired; a drift
    observation ages on its LAST observation, so a still-recurring drift is
    never expired. Deleted ids are table-prefixed so the digest cannot
    collide across tables within the one family event.
    """

    audit = get_audit_store()
    ops = get_provider_operations_store()
    prompts = get_prompt_repository()
    async_runtime = get_async_runtime_store()
    kill_switches = get_kill_switch_repository()
    registry = get_workflow_pack_registry_store()
    catalogue = get_model_catalogue_repository()
    confirmations = get_provider_retention_confirmation_store()

    deleted: list[str] = []
    details: list[str] = []

    def _expire(table: str, rows: list[tuple[str, str]], delete_fn: object) -> None:
        expired = [pk for pk, instant in rows if _is_before(instant, cutoff)]
        if expired:
            count = delete_fn(expired)  # type: ignore[operator]
            deleted.extend(f"{table}:{pk}" for pk in expired)
            details.append(f"{table}={count}")

    _expire(
        "audit_access_events",
        [
            (e.event_id, e.recorded_at)
            for e in audit.list_access_events(limit=_CANDIDATE_BATCH_LIMIT)
        ],
        audit.delete_access_events,
    )
    _expire(
        "data_lifecycle_events",
        [
            (e.event_id, e.recorded_at)
            for e in audit.list_lifecycle_events(limit=_CANDIDATE_BATCH_LIMIT)
        ],
        audit.delete_lifecycle_events,
    )
    _expire(
        "provider_operations_events",
        [
            (e.event_id, e.recorded_at)
            for e in ops.list_operations_events(limit=_CANDIDATE_BATCH_LIMIT)
        ],
        ops.delete_operations_events,
    )
    # Attempt-debit evidence (issue #289) expires like the rest of the
    # family; deleting evidence never reverses the budget counter.
    _expire(
        "provider_attempt_debits",
        [
            (d.debit_id, d.recorded_at)
            for d in ops.list_attempt_debits(limit=_CANDIDATE_BATCH_LIMIT)
        ],
        ops.delete_attempt_debits,
    )
    _expire(
        "provider_governed_actions",
        [
            (a.action_id, a.requested_at)
            for a in ops.list_governed_actions(
                status=None, target=None, limit=_CANDIDATE_BATCH_LIMIT
            )
            if a.status.value != "PENDING"
        ],
        ops.delete_governed_actions,
    )
    _expire(
        "prompt_rollout_events",
        [
            (e.event_id, e.recorded_at)
            for e in prompts.list_prompt_rollout_events(limit=_CANDIDATE_BATCH_LIMIT)
        ],
        prompts.delete_prompt_rollout_events,
    )
    _expire(
        "async_control_events",
        [
            (e.event_id, e.recorded_at)
            for e in async_runtime.list_control_events(limit=_CANDIDATE_BATCH_LIMIT)
        ],
        async_runtime.delete_control_events,
    )
    _expire(
        "kill_switch_activations",
        [
            (a.switch_id, a.activated_at)
            for a in kill_switches.list_activations()
            if a.cleared_at is not None or a.expiry_recorded_at is not None
        ],
        kill_switches.delete_activations,
    )
    _expire(
        "workflow_pack_control_events",
        [
            (e.event_id, e.recorded_at)
            for e in registry.list_control_events(limit=_CANDIDATE_BATCH_LIMIT)
        ],
        registry.delete_control_events,
    )
    _expire(
        "model_catalogue_lifecycle_events",
        [
            (e.event_id, e.recorded_at)
            for e in catalogue.list_all_lifecycle_events(limit=_CANDIDATE_BATCH_LIMIT)
        ],
        catalogue.delete_lifecycle_events,
    )
    _expire(
        "model_revision_drift_observations",
        [
            (o.observation_id, o.last_observed_at)
            for o in catalogue.list_all_drift_observations(limit=_CANDIDATE_BATCH_LIMIT)
        ],
        catalogue.delete_drift_observations,
    )
    _expire(
        "provider_retention_confirmations",
        [
            (c.envelope.claims.confirmation_id, c.envelope.claims.issued_at_utc)
            for c in confirmations.list_confirmations(limit=_CANDIDATE_BATCH_LIMIT)
        ],
        confirmations.delete_confirmations,
    )
    detail = "; ".join(details) if details else "nothing past retention"
    return deleted, (
        f"expired control-plane evidence ({detail}); enforcing switches, pending "
        "governed actions and recently-observed drift are never expired"
    )


def _held_tenants(family: RetentionFamily) -> set[str]:
    return {
        hold.key_value
        for hold in get_audit_store().list_active_legal_holds(family_id=family.family_id)
        if hold.key_type == "tenant"
    }


def _expire_workflow_run_records(
    family: RetentionFamily, cutoff: datetime
) -> tuple[list[str], str]:
    """Business run records past retention, honouring tenant-scoped holds.

    Run events and flow checkpoints cascade with their parent - an event of a
    held run stays regardless of its own age. Idempotency claims and queue
    events age independently under the same tenant holds.
    """

    held = _held_tenants(family)
    deleted: list[str] = []
    details: list[str] = []

    runs = get_workflow_pack_run_store()
    expired_runs = [
        record.run_id
        for record in runs.list_runs(limit=_CANDIDATE_BATCH_LIMIT)
        if _is_before(record.created_at, cutoff)
        and (record.tenant_id is None or record.tenant_id not in held)
    ]
    if expired_runs:
        run_count, event_count = runs.delete_runs_with_events(expired_runs)
        deleted.extend(f"workflow_pack_runs:{run_id}" for run_id in expired_runs)
        details.append(f"runs={run_count} run_events={event_count}")

    flows = get_workflow_pack_task_flow_store()
    expired_flows = [
        record.descriptor.task_flow_id
        for record in flows.list_task_flows()
        if _is_before(record.descriptor.created_at, cutoff)
        and (record.descriptor.tenant_id is None or record.descriptor.tenant_id not in held)
    ]
    if expired_flows:
        flow_count, checkpoint_count = flows.delete_task_flows_with_checkpoints(expired_flows)
        deleted.extend(f"workflow_pack_task_flows:{flow_id}" for flow_id in expired_flows)
        details.append(f"task_flows={flow_count} checkpoints={checkpoint_count}")

    queue_events = get_workflow_pack_queue_event_store()
    expired_queue_events = [
        record.descriptor.event_id
        for record in queue_events.list_events(limit=_CANDIDATE_BATCH_LIMIT)
        if _is_before(record.descriptor.recorded_at, cutoff)
        and (record.descriptor.tenant_id is None or record.descriptor.tenant_id not in held)
    ]
    if expired_queue_events:
        count = queue_events.delete_events(expired_queue_events)
        deleted.extend(
            f"workflow_pack_queue_events:{event_id}" for event_id in expired_queue_events
        )
        details.append(f"queue_events={count}")

    idempotency = get_workflow_pack_execution_idempotency_store()
    expired_idempotency = [
        record.record_id
        for record in idempotency.list_records(limit=_CANDIDATE_BATCH_LIMIT)
        if _is_before(record.created_at, cutoff)
        and (record.tenant_scope is None or record.tenant_scope not in held)
    ]
    if expired_idempotency:
        count = idempotency.delete_records(expired_idempotency)
        deleted.extend(
            f"workflow_pack_execution_idempotency:{record_id}" for record_id in expired_idempotency
        )
        details.append(f"idempotency={count}")

    detail = "; ".join(details) if details else "nothing past retention"
    return deleted, (
        f"expired workflow run records ({detail}); held tenants and cascading "
        "children of held runs are untouched"
    )


def _expire_artifact_content(family: RetentionFamily, cutoff: datetime) -> tuple[list[str], str]:
    """Aged artifacts, except rows retained for review (live obligation).

    Payload bytes and metadata go together (issue #291): the row is the only
    pointer to the object, so expiring metadata alone would orphan content
    the family's retention claim says is gone.
    """

    from app.services.artifact_payloads import delete_artifacts_with_payloads

    repository = get_artifact_repository()
    expired = [
        record
        for record in repository.list_artifacts()
        if _is_before(record.created_at, cutoff)
        and record.retention_posture != "retained_for_review"
    ]
    count = delete_artifacts_with_payloads(expired) if expired else 0
    return [f"artifact_metadata:{record.artifact_id}" for record in expired], (
        f"expired {count} artifact rows with their payload objects; "
        "retained_for_review rows are never expired"
    )


def _expire_evaluation_approval_evidence(
    family: RetentionFamily, cutoff: datetime
) -> tuple[list[str], str]:
    """Evaluation runs past retention, cascading attempts and any case rows."""

    repository = get_evaluation_runtime_store()
    expired_runs = [
        record.run_id
        for record in repository.list_runs()
        if _is_before(record.submitted_at, cutoff)
    ]
    runs, attempts, cases = (
        repository.delete_runs_with_dependents(expired_runs) if expired_runs else (0, 0, 0)
    )
    return [f"evaluation_runs:{run_id}" for run_id in expired_runs], (
        f"expired {runs} evaluation runs with {attempts} attempts and {cases} case rows"
    )


def _expire_evaluation_case_content(
    family: RetentionFamily, cutoff: datetime
) -> tuple[list[str], str]:
    """Bulky per-case content ages on its own instant; the run verdict stays.

    Minimisation (issue #158, S4): a PASSING case's content ages out at the
    family's declared minimised horizon - it has no diagnostic purpose beyond
    review - while failures keep the full period for defect forensics.
    """

    minimised_cutoff = cutoff
    if family.minimised_retention_days is not None:
        assert family.retention_days is not None  # pinned by policy validation
        now = cutoff + timedelta(days=family.retention_days)
        minimised_cutoff = now - timedelta(days=family.minimised_retention_days)
    repository = get_evaluation_runtime_store()
    expired: list[str] = []
    minimised = 0
    for record in repository.list_all_case_results(limit=_CANDIDATE_BATCH_LIMIT):
        if _is_before(record.recorded_at, cutoff):
            expired.append(record.case_result_id)
        elif record.outcome == "PASS" and _is_before(record.recorded_at, minimised_cutoff):
            expired.append(record.case_result_id)
            minimised += 1
    count = repository.delete_case_results(expired) if expired else 0
    return [f"evaluation_case_results:{case_id}" for case_id in expired], (
        f"expired {count} evaluation case rows ({minimised} passing cases at the "
        "minimised horizon); run verdicts remain with the approval evidence family"
    )


def _expire_retrieval_reference_history(
    family: RetentionFamily, cutoff: datetime
) -> tuple[list[str], str]:
    """Superseded version history and ingestion-job records past retention.

    Only SUPERSEDED versions age out - the current version of a document is
    live reference state and never expired by lifecycle, whatever its age.
    """

    repository = get_retrieval_repository()
    deleted: list[str] = []
    expired_versions = [
        version.version_id
        for version in repository.list_document_versions()
        if version.lifecycle_status.value == "SUPERSEDED" and _is_before(version.created_at, cutoff)
    ]
    version_count = repository.delete_document_versions(expired_versions) if expired_versions else 0
    deleted.extend(f"retrieval_document_versions:{vid}" for vid in expired_versions)
    expired_jobs = [
        job.job_id
        for job in repository.list_ingestion_jobs()
        if _is_before(job.requested_at, cutoff)
    ]
    job_count = repository.delete_ingestion_jobs(expired_jobs) if expired_jobs else 0
    deleted.extend(f"retrieval_ingestion_jobs:{jid}" for jid in expired_jobs)
    return deleted, (
        f"expired {version_count} superseded document versions and {job_count} ingestion "
        "jobs; current versions are live reference state and never expired"
    )


_ENFORCED_FAMILY_HANDLERS = {
    "audit_evidence": _expire_audit_evidence,
    "control_plane_evidence": _expire_control_plane_evidence,
    "workflow_run_records": _expire_workflow_run_records,
    "artifact_content": _expire_artifact_content,
    "evaluation_approval_evidence": _expire_evaluation_approval_evidence,
    "evaluation_case_content": _expire_evaluation_case_content,
    "retrieval_shared_reference": _expire_retrieval_reference_history,
    "async_runtime_content": _expire_async_runtime_content,
    "transient_operational_leases": _expire_transient_leases,
}


def enforced_family_handler_ids() -> frozenset[str]:
    """The families the engine actually applies - pinned against the policy."""

    return frozenset(_ENFORCED_FAMILY_HANDLERS)


# Families whose handler honours a declared minimised horizon (issue #158,
# S4). Pinned bidirectionally against the policy by test: a declared
# minimisation without a handler behind it would be a claim the engine does
# not keep.
MINIMISING_FAMILY_HANDLER_IDS = frozenset({"evaluation_case_content"})


def _record_deletion_evidence(
    *,
    family: RetentionFamily,
    policy_version: str,
    actor: str,
    deleted_ids: list[str],
    now: datetime,
) -> str:
    digest = hashlib.sha256("\n".join(sorted(deleted_ids)).encode("utf-8")).hexdigest()
    event = DataLifecycleEventRecord(
        event_id=f"dle_{uuid4().hex[:16]}",
        family_id=family.family_id,
        action=DataLifecycleAction.EXPIRY,
        key_scope=None,
        row_count=len(deleted_ids),
        policy_version=policy_version,
        actor=actor,
        deleted_ids_digest=digest,
        recorded_at=now.isoformat(),
    )
    get_audit_store().save_lifecycle_event(event)
    return event.event_id


def _is_before(instant: str, cutoff: datetime) -> bool:
    """Parse-and-compare: never a string comparison across ISO variants."""

    try:
        parsed = datetime.fromisoformat(instant.replace("Z", "+00:00"))
    except ValueError:
        # An unparseable instant is never silently expired.
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed < cutoff
