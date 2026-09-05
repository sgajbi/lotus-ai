"""Split-runtime shared-state visibility (issue #331, audit F7).

The advertised split deployment runs API and worker as separate processes:
every store both of them read must be durable. These tests pin the exact
failure mechanism the audit reproduced - the worker looking up
ADMISSION_QUEUED queue-event truth the API wrote - across two INDEPENDENT
SQL repository instances (separate engines on one database, the repo's
established cross-replica idiom), and pin the memory topology's blindness
as the defect the startup fence now refuses.
"""

from __future__ import annotations

from pathlib import Path

from app.contracts.workflow_pack_queue_policies import (
    WorkflowPackQueueEventDescriptor,
    WorkflowPackQueueEventType,
    WorkflowPackQueueLane,
    WorkflowPackQueueState,
)
from app.repositories.memory_workflow_pack_queue_event_repository import (
    InMemoryWorkflowPackQueueEventRepository,
)
from app.repositories.sqlalchemy_workflow_pack_queue_event_repository import (
    SqlAlchemyWorkflowPackQueueEventRepository,
)
from app.repositories.workflow_pack_queue_event_repository import (
    WorkflowPackQueueEventRecord,
)
from tests.support.migration_runner import upgrade_database_to_head


def _admission_queued(event_id: str, queue_item_id: str) -> WorkflowPackQueueEventRecord:
    return WorkflowPackQueueEventRecord(
        descriptor=WorkflowPackQueueEventDescriptor(
            event_id=event_id,
            queue_item_id=queue_item_id,
            event_type=WorkflowPackQueueEventType.ADMISSION_QUEUED,
            policy_id="queue-policy.idea-explanation.v1",
            workflow_pack_id="idea_explanation.pack",
            workflow_pack_version="v1",
            lane=WorkflowPackQueueLane.LATENCY_SENSITIVE,
            state=WorkflowPackQueueState.QUEUED,
            caller_app="lotus-idea",
            correlation_id="corr-split-visibility-1",
            tenant_id="tenant-sg-001",
            workflow_surface="idea-review-panel",
            reason_code=None,
            message="Admission queued.",
            recorded_at="2026-09-05T12:00:00Z",
        )
    )


def test_durable_queue_events_are_visible_across_processes(tmp_path: Path) -> None:
    """The API process writes ADMISSION_QUEUED; a SEPARATE worker process
    (independent repository instance, fresh engine, same database) must see
    it - this is the lookup `build_workflow_pack_queue_event_detail`
    performs before executing a queued job."""

    database_url = f"sqlite:///{tmp_path / 'split-visibility.db'}"
    upgrade_database_to_head(database_url)
    api_process = SqlAlchemyWorkflowPackQueueEventRepository(database_url)
    worker_process = SqlAlchemyWorkflowPackQueueEventRepository(database_url)

    api_process.save_event(_admission_queued("wqe_split_1", "wqi_split_1"))

    seen = worker_process.list_events(queue_item_id="wqi_split_1")
    assert [event.descriptor.event_id for event in seen] == ["wqe_split_1"]
    assert seen[0].descriptor.event_type is WorkflowPackQueueEventType.ADMISSION_QUEUED


def test_memory_queue_events_are_process_local_which_is_why_split_mode_refuses_them(
    tmp_path: Path,
) -> None:
    """The defect pinned as truth: two memory repositories are two separate
    worlds - the worker's lookup finds nothing. This blindness is exactly
    what the split-runtime startup fence (test_startup_policy) now refuses
    to boot."""

    api_process = InMemoryWorkflowPackQueueEventRepository()
    worker_process = InMemoryWorkflowPackQueueEventRepository()

    api_process.save_event(_admission_queued("wqe_split_2", "wqi_split_2"))

    assert worker_process.list_events(queue_item_id="wqi_split_2") == []
