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


_ENFORCED_FAMILY_HANDLERS = {
    "audit_evidence": _expire_audit_evidence,
    "async_runtime_content": _expire_async_runtime_content,
    "transient_operational_leases": _expire_transient_leases,
}


def enforced_family_handler_ids() -> frozenset[str]:
    """The families the engine actually applies - pinned against the policy."""

    return frozenset(_ENFORCED_FAMILY_HANDLERS)


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
