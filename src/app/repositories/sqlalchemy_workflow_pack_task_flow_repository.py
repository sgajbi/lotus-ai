from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.contracts.workflow_pack_task_flows import (
    WorkflowPackTaskFlowCheckpointDescriptor,
    WorkflowPackTaskFlowDescriptor,
)
from app.db.models import WorkflowPackTaskFlowCheckpointModel, WorkflowPackTaskFlowModel
from app.repositories.sqlalchemy_repository_base import SqlAlchemyRepositoryBase
from app.repositories.workflow_pack_task_flow_repository import (
    WorkflowPackTaskFlowCheckpointRecord,
    WorkflowPackTaskFlowRecord,
    WorkflowPackTaskFlowRepository,
)


class SqlAlchemyWorkflowPackTaskFlowRepository(
    SqlAlchemyRepositoryBase, WorkflowPackTaskFlowRepository
):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._ensure_sqlite_parent_directory()
        self._configure_sqlalchemy(database_url)

    def list_task_flows(self) -> list[WorkflowPackTaskFlowRecord]:
        with self._session_factory() as session:
            models = session.scalars(
                select(WorkflowPackTaskFlowModel).order_by(WorkflowPackTaskFlowModel.created_at)
            ).all()
            return [self._to_task_flow_record(model) for model in models]

    def query_task_flows(
        self,
        *,
        workflow_pack_id: str | None = None,
        caller: str | None = None,
        tenant_id: str | None = None,
        workflow_surface: str | None = None,
        flow_status: str | None = None,
        supportability_status: str | None = None,
        limit: int,
    ) -> list[WorkflowPackTaskFlowRecord]:
        statement = select(WorkflowPackTaskFlowModel)
        if workflow_pack_id is not None:
            statement = statement.where(
                WorkflowPackTaskFlowModel.workflow_pack_id == workflow_pack_id
            )
        if caller is not None:
            statement = statement.where(WorkflowPackTaskFlowModel.caller == caller)
        if tenant_id is not None:
            statement = statement.where(WorkflowPackTaskFlowModel.tenant_id == tenant_id)
        if workflow_surface is not None:
            statement = statement.where(
                WorkflowPackTaskFlowModel.workflow_surface == workflow_surface
            )
        if flow_status is not None:
            statement = statement.where(WorkflowPackTaskFlowModel.flow_status == flow_status)
        if supportability_status is not None:
            statement = statement.where(
                WorkflowPackTaskFlowModel.supportability_status == supportability_status
            )
        statement = statement.order_by(
            WorkflowPackTaskFlowModel.updated_at.desc(),
            WorkflowPackTaskFlowModel.created_at.desc(),
            WorkflowPackTaskFlowModel.task_flow_id.desc(),
        ).limit(max(limit, 0))
        with self._session_factory() as session:
            models = session.scalars(statement).all()
            return [self._to_task_flow_record(model) for model in models]

    def list_task_flows_by_run_ref(
        self, *, run_id: str, limit: int
    ) -> list[WorkflowPackTaskFlowRecord]:
        statement = (
            select(WorkflowPackTaskFlowModel)
            .order_by(
                WorkflowPackTaskFlowModel.updated_at.desc(),
                WorkflowPackTaskFlowModel.created_at.desc(),
                WorkflowPackTaskFlowModel.task_flow_id.desc(),
            )
            .limit(max(limit, 0))
        )
        with self._session_factory() as session:
            models = session.scalars(statement).all()
            return [
                record
                for record in (self._to_task_flow_record(model) for model in models)
                if run_id in record.descriptor.run_refs
            ]

    def get_task_flow(self, *, task_flow_id: str) -> WorkflowPackTaskFlowRecord | None:
        with self._session_factory() as session:
            model = session.get(WorkflowPackTaskFlowModel, task_flow_id)
            if model is None:
                return None
            return self._to_task_flow_record(model)

    def save_task_flow(self, record: WorkflowPackTaskFlowRecord) -> None:
        descriptor = record.descriptor
        model = WorkflowPackTaskFlowModel(
            task_flow_id=descriptor.task_flow_id,
            workflow_pack_id=descriptor.workflow_pack_id,
            workflow_pack_version=descriptor.workflow_pack_version,
            caller=descriptor.caller,
            tenant_id=descriptor.tenant_id,
            workflow_surface=descriptor.workflow_surface,
            workflow_authority_owner=descriptor.workflow_authority_owner,
            flow_status=descriptor.flow_status.value,
            supportability_status=descriptor.supportability_status.value,
            current_step_id=descriptor.current_step_id,
            created_at=descriptor.created_at,
            updated_at=descriptor.updated_at,
            expires_at=descriptor.expires_at,
            descriptor_payload=descriptor.model_dump(mode="json"),
        )
        with self._session_factory() as session:
            session.merge(model)
            session.commit()

    def list_checkpoints(self, *, task_flow_id: str) -> list[WorkflowPackTaskFlowCheckpointRecord]:
        with self._session_factory() as session:
            models = session.scalars(
                select(WorkflowPackTaskFlowCheckpointModel)
                .where(WorkflowPackTaskFlowCheckpointModel.task_flow_id == task_flow_id)
                .order_by(WorkflowPackTaskFlowCheckpointModel.recorded_at)
            ).all()
            return [self._to_checkpoint_record(model) for model in models]

    def save_checkpoint(self, record: WorkflowPackTaskFlowCheckpointRecord) -> None:
        descriptor = record.descriptor
        model = WorkflowPackTaskFlowCheckpointModel(
            checkpoint_id=descriptor.checkpoint_id,
            task_flow_id=descriptor.task_flow_id,
            step_id=descriptor.step_id,
            transition=descriptor.transition.value,
            actor=descriptor.actor,
            recorded_at=descriptor.recorded_at,
            degraded=descriptor.degraded,
            unsupported=descriptor.unsupported,
            descriptor_payload=descriptor.model_dump(mode="json"),
        )
        with self._session_factory() as session:
            session.merge(model)
            session.commit()

    def _to_task_flow_record(self, model: WorkflowPackTaskFlowModel) -> WorkflowPackTaskFlowRecord:
        return WorkflowPackTaskFlowRecord(
            descriptor=WorkflowPackTaskFlowDescriptor.model_validate(model.descriptor_payload)
        )

    def _to_checkpoint_record(
        self, model: WorkflowPackTaskFlowCheckpointModel
    ) -> WorkflowPackTaskFlowCheckpointRecord:
        return WorkflowPackTaskFlowCheckpointRecord(
            descriptor=WorkflowPackTaskFlowCheckpointDescriptor.model_validate(
                model.descriptor_payload
            )
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
