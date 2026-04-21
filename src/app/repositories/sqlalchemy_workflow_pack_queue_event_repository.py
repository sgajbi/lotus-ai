from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.contracts.workflow_pack_queue_policies import WorkflowPackQueueEventDescriptor
from app.db.models import WorkflowPackQueueEventModel
from app.repositories.sqlalchemy_repository_base import SqlAlchemyRepositoryBase
from app.repositories.workflow_pack_queue_event_repository import (
    WorkflowPackQueueEventRecord,
    WorkflowPackQueueEventRepository,
)


class SqlAlchemyWorkflowPackQueueEventRepository(
    SqlAlchemyRepositoryBase, WorkflowPackQueueEventRepository
):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._ensure_sqlite_parent_directory()
        self._configure_sqlalchemy(database_url)

    def list_events(
        self,
        *,
        queue_item_id: str | None = None,
        workflow_pack_id: str | None = None,
        limit: int = 100,
    ) -> list[WorkflowPackQueueEventRecord]:
        statement = select(WorkflowPackQueueEventModel)
        if queue_item_id is not None:
            statement = statement.where(WorkflowPackQueueEventModel.queue_item_id == queue_item_id)
        if workflow_pack_id is not None:
            statement = statement.where(
                WorkflowPackQueueEventModel.workflow_pack_id == workflow_pack_id
            )
        statement = statement.order_by(
            WorkflowPackQueueEventModel.recorded_at.desc(),
            WorkflowPackQueueEventModel.event_id.desc(),
        ).limit(limit)
        with self._session_factory() as session:
            models = session.scalars(statement).all()
            return [self._to_record(model) for model in models]

    def save_event(self, record: WorkflowPackQueueEventRecord) -> None:
        descriptor = record.descriptor
        model = WorkflowPackQueueEventModel(
            event_id=descriptor.event_id,
            queue_item_id=descriptor.queue_item_id,
            event_type=descriptor.event_type.value,
            policy_id=descriptor.policy_id,
            workflow_pack_id=descriptor.workflow_pack_id,
            workflow_pack_version=descriptor.workflow_pack_version,
            lane=descriptor.lane.value if descriptor.lane is not None else None,
            state=descriptor.state.value,
            caller_app=descriptor.caller_app,
            correlation_id=descriptor.correlation_id,
            tenant_id=descriptor.tenant_id,
            workflow_surface=descriptor.workflow_surface,
            reason_code=descriptor.reason_code,
            message=descriptor.message,
            recorded_at=descriptor.recorded_at,
            descriptor_payload=descriptor.model_dump(mode="json"),
        )
        with self._session_factory() as session:
            session.merge(model)
            session.commit()

    def _to_record(self, model: WorkflowPackQueueEventModel) -> WorkflowPackQueueEventRecord:
        return WorkflowPackQueueEventRecord(
            descriptor=WorkflowPackQueueEventDescriptor.model_validate(model.descriptor_payload)
        )

    def _ensure_sqlite_parent_directory(self) -> None:
        prefix = "sqlite:///"
        if not self._database_url.startswith(prefix):
            return
        db_path = self._database_url.removeprefix(prefix)
        if db_path == ":memory:":
            return
        path = Path(db_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        path.parent.mkdir(parents=True, exist_ok=True)
