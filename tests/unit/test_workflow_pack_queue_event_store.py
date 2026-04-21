from pathlib import Path

from sqlalchemy import create_engine

from app.db.base import Base
import app.db.models  # noqa: F401
from app.contracts.workflow_pack_queue_policies import (
    WorkflowPackQueueEventDescriptor,
    WorkflowPackQueueEventType,
    WorkflowPackQueueLane,
    WorkflowPackQueueState,
)
from app.repositories.sqlalchemy_workflow_pack_queue_event_repository import (
    SqlAlchemyWorkflowPackQueueEventRepository,
)
from app.repositories.workflow_pack_queue_event_repository import (
    WorkflowPackQueueEventRecord,
)


def _queue_event(event_id: str, queue_item_id: str) -> WorkflowPackQueueEventRecord:
    return WorkflowPackQueueEventRecord(
        descriptor=WorkflowPackQueueEventDescriptor(
            event_id=event_id,
            queue_item_id=queue_item_id,
            event_type=WorkflowPackQueueEventType.ADMISSION_GRANTED,
            policy_id="queue-policy.advisor-brief.v1",
            workflow_pack_id="advisor_brief.pack",
            workflow_pack_version="v1",
            lane=WorkflowPackQueueLane.LATENCY_SENSITIVE,
            state=WorkflowPackQueueState.RUNNING,
            caller_app="lotus-gateway",
            correlation_id="corr-queue-store-1",
            tenant_id="tenant-sg-001",
            workflow_surface="advisor-brief-panel",
            reason_code=None,
            message="Admission granted.",
            recorded_at="2026-04-21T08:00:00Z",
        )
    )


def test_sqlalchemy_queue_event_repository_persists_restart_safe_history(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'queue-events.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    engine.dispose()

    first_repository = SqlAlchemyWorkflowPackQueueEventRepository(database_url)
    first_repository.save_event(_queue_event("event-1", "wpq_1"))

    second_repository = SqlAlchemyWorkflowPackQueueEventRepository(database_url)
    records = second_repository.list_events(queue_item_id="wpq_1")

    assert len(records) == 1
    assert records[0].descriptor.event_id == "event-1"
    assert records[0].descriptor.caller_app == "lotus-gateway"
    assert records[0].descriptor.workflow_surface == "advisor-brief-panel"


def test_sqlalchemy_queue_event_repository_filters_by_pack_and_limit(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'queue-events-filtered.db'}"
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    engine.dispose()

    repository = SqlAlchemyWorkflowPackQueueEventRepository(database_url)
    repository.save_event(_queue_event("event-1", "wpq_1"))
    repository.save_event(_queue_event("event-2", "wpq_2"))

    records = repository.list_events(workflow_pack_id="advisor_brief.pack", limit=1)

    assert len(records) == 1
    assert records[0].descriptor.event_id == "event-2"
