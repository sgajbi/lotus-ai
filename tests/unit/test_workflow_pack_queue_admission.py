from fastapi import HTTPException

from app.contracts.workflow_packs import WorkflowPackRegistrationDescriptor
from app.contracts.workflow_pack_queue_policies import WorkflowPackQueueLane
from app.services.workflow_pack_queue_admission import (
    acquire_workflow_pack_queue_admission,
    release_workflow_pack_queue_admission,
)
from app.services.workflow_pack_registry import get_workflow_pack_registration


def _advisor_brief_registration() -> WorkflowPackRegistrationDescriptor:
    registration = get_workflow_pack_registration(pack_id="advisor_brief.pack", version="v1")
    assert registration is not None
    return registration


def test_queue_admission_acquires_and_releases_default_lane() -> None:
    lease = acquire_workflow_pack_queue_admission(registration=_advisor_brief_registration())

    assert lease.policy_id == "queue-policy.advisor-brief.v1"
    assert lease.workflow_pack_id == "advisor_brief.pack"
    assert lease.workflow_pack_version == "v1"
    assert lease.lane == WorkflowPackQueueLane.LATENCY_SENSITIVE
    assert lease.state.value == "RUNNING"

    release_workflow_pack_queue_admission(lease.queue_item_id)


def test_queue_admission_rejects_lane_capacity_without_creating_extra_lease() -> None:
    registration = _advisor_brief_registration()
    first_lease = acquire_workflow_pack_queue_admission(registration=registration)
    second_lease = acquire_workflow_pack_queue_admission(registration=registration)

    try:
        try:
            acquire_workflow_pack_queue_admission(registration=registration)
        except HTTPException as exc:
            assert exc.status_code == 429
            assert "max_concurrent_runs_per_lane" in str(exc.detail)
            assert "advisor_brief.pack@v1" in str(exc.detail)
        else:
            raise AssertionError("Expected queue admission to reject full lane capacity")
    finally:
        release_workflow_pack_queue_admission(first_lease.queue_item_id)
        release_workflow_pack_queue_admission(second_lease.queue_item_id)


def test_queue_admission_rejects_unsupported_requested_lane() -> None:
    try:
        acquire_workflow_pack_queue_admission(
            registration=_advisor_brief_registration(),
            requested_lane=WorkflowPackQueueLane.NIGHTLY,
        )
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "not allowed" in str(exc.detail)
    else:
        raise AssertionError("Expected unsupported queue lane to fail admission")
