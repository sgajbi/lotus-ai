"""Replica-shared workflow-pack admission leases (issue #153, S3)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.contracts.workflow_pack_queue_policies import (
    WorkflowPackQueueLane,
    WorkflowPackQueueState,
)
from app.repositories.sqlalchemy_workflow_pack_admission_lease_repository import (
    SqlAlchemyWorkflowPackAdmissionLeaseRepository,
)
from app.services.workflow_pack_queue_admission_models import (
    WorkflowPackQueueAdmissionLease,
)
from tests.support.migration_runner import upgrade_database_to_head


def _lease(
    queue_item_id: str,
    *,
    lane: WorkflowPackQueueLane,
    admitted_at: str | None = None,
) -> WorkflowPackQueueAdmissionLease:
    return WorkflowPackQueueAdmissionLease(
        queue_item_id=queue_item_id,
        policy_id="advisor_brief.policy",
        workflow_pack_id="advisor_brief.pack",
        workflow_pack_version="v1",
        lane=lane,
        state=WorkflowPackQueueState.RUNNING,
        admitted_at=admitted_at or datetime.now(UTC).isoformat(),
        caller_app="lotus-gateway",
        correlation_id="corr-lease-1",
        tenant_id="tenant-sg-001",
        workflow_surface="advisor-brief-workspace",
    )


def _two_repositories(
    tmp_path: Path,
) -> tuple[
    SqlAlchemyWorkflowPackAdmissionLeaseRepository,
    SqlAlchemyWorkflowPackAdmissionLeaseRepository,
]:
    database_url = f"sqlite:///{tmp_path / 'admission-leases.db'}"
    upgrade_database_to_head(database_url)
    # Two independent instances model two replicas sharing one database.
    return (
        SqlAlchemyWorkflowPackAdmissionLeaseRepository(database_url),
        SqlAlchemyWorkflowPackAdmissionLeaseRepository(database_url),
    )


def test_two_replicas_share_one_admission_capacity(tmp_path: Path) -> None:
    first, second = _two_repositories(tmp_path)
    lane = WorkflowPackQueueLane.LATENCY_SENSITIVE

    granted = first.try_admit(_lease("wpq_1", lane=lane), pack_limit=1, lane_limit=1)
    assert granted.admitted is True

    # The second replica sees the first replica's lease: a single shared
    # capacity, which the process-local dict could never provide.
    refused = second.try_admit(_lease("wpq_2", lane=lane), pack_limit=1, lane_limit=1)
    assert refused.admitted is False
    assert refused.active_pack_count == 1

    second.delete_lease("wpq_1")
    after_release = second.try_admit(_lease("wpq_3", lane=lane), pack_limit=1, lane_limit=1)
    assert after_release.admitted is True


def test_lane_limit_binds_independently_of_pack_limit(tmp_path: Path) -> None:
    first, second = _two_repositories(tmp_path)

    assert first.try_admit(
        _lease("wpq_a", lane=WorkflowPackQueueLane.LATENCY_SENSITIVE), pack_limit=5, lane_limit=1
    ).admitted
    lane_refused = second.try_admit(
        _lease("wpq_b", lane=WorkflowPackQueueLane.LATENCY_SENSITIVE), pack_limit=5, lane_limit=1
    )
    assert lane_refused.admitted is False
    assert lane_refused.active_lane_count == 1

    other_lane = second.try_admit(
        _lease("wpq_c", lane=WorkflowPackQueueLane.BATCH), pack_limit=5, lane_limit=1
    )
    assert other_lane.admitted is True


def test_lease_round_trips_with_artifact_refs_across_instances(tmp_path: Path) -> None:
    first, second = _two_repositories(tmp_path)
    lease = _lease("wpq_rt", lane=WorkflowPackQueueLane.LATENCY_SENSITIVE)

    assert first.try_admit(lease, pack_limit=2, lane_limit=2).admitted
    loaded = second.get_lease("wpq_rt")

    assert loaded == lease
    assert [item.queue_item_id for item in second.list_leases()] == ["wpq_rt"]


def test_a_lease_older_than_its_ttl_is_reclaimed(tmp_path: Path) -> None:
    """A replica that dies mid-execution must not hold capacity forever.

    The process-local dict provided this for free by dying with the process;
    the durable store has to reclaim explicitly (issue #228).
    """

    first, second = _two_repositories(tmp_path)
    lane = WorkflowPackQueueLane.LATENCY_SENSITIVE
    abandoned = (datetime.now(UTC) - timedelta(seconds=7200)).isoformat()

    assert first.try_admit(
        _lease("wpq_crashed", lane=lane, admitted_at=abandoned), pack_limit=1, lane_limit=1
    ).admitted

    # The holder is gone; the next admission reclaims the expired lease and
    # capacity recovers instead of being permanently consumed.
    recovered = second.try_admit(_lease("wpq_next", lane=lane), pack_limit=1, lane_limit=1)
    assert recovered.admitted is True
    assert second.get_lease("wpq_crashed") is None


def test_a_live_lease_within_its_ttl_still_binds_capacity(tmp_path: Path) -> None:
    first, second = _two_repositories(tmp_path)
    lane = WorkflowPackQueueLane.LATENCY_SENSITIVE
    recent = (datetime.now(UTC) - timedelta(seconds=60)).isoformat()

    assert first.try_admit(
        _lease("wpq_live", lane=lane, admitted_at=recent), pack_limit=1, lane_limit=1
    ).admitted
    refused = second.try_admit(_lease("wpq_blocked", lane=lane), pack_limit=1, lane_limit=1)
    assert refused.admitted is False


def test_only_one_caller_claims_a_terminal_transition(tmp_path: Path) -> None:
    """Concurrent release and cancel both observe the lease; the delete is the
    atomic claim, so exactly one of them records the terminal event."""

    first, second = _two_repositories(tmp_path)
    lane = WorkflowPackQueueLane.LATENCY_SENSITIVE
    assert first.try_admit(_lease("wpq_terminal", lane=lane), pack_limit=1, lane_limit=1).admitted

    assert first.delete_lease("wpq_terminal") is True
    assert second.delete_lease("wpq_terminal") is False


def test_concurrent_first_admissions_do_not_race_on_the_guard_row(tmp_path: Path) -> None:
    """Both replicas may find no guard row for a policy and try to create it;
    the loser's integrity error must resolve into locking the winner's row,
    not escape as a server error."""

    first, second = _two_repositories(tmp_path)
    lane = WorkflowPackQueueLane.BATCH

    assert first.try_admit(_lease("wpq_guard_1", lane=lane), pack_limit=2, lane_limit=2).admitted
    assert second.try_admit(_lease("wpq_guard_2", lane=lane), pack_limit=2, lane_limit=2).admitted
