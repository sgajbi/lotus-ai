from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.contracts.artifacts import ArtifactDescriptor
from app.contracts.evidence import ExecutionEvidenceDescriptor
from app.db.models import WorkflowPackRunEventModel, WorkflowPackRunModel
from app.repositories.sqlalchemy_repository_base import SqlAlchemyRepositoryBase
from app.repositories.workflow_pack_run_repository import (
    WorkflowPackRunEventRecord,
    WorkflowPackRunRecord,
    WorkflowPackRunRepository,
)


class SqlAlchemyWorkflowPackRunRepository(SqlAlchemyRepositoryBase, WorkflowPackRunRepository):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._ensure_sqlite_parent_directory()
        self._configure_sqlalchemy(database_url)

    def list_runs(self, *, limit: int | None = None) -> list[WorkflowPackRunRecord]:
        with self._session_factory() as session:
            statement = select(WorkflowPackRunModel)
            if limit is not None:
                statement = statement.order_by(WorkflowPackRunModel.created_at.desc()).limit(
                    max(limit, 0)
                )
            else:
                statement = statement.order_by(WorkflowPackRunModel.created_at)
            models = session.scalars(statement).all()
            return [self._to_run_record(model) for model in models]

    def query_runs(
        self,
        *,
        registration_ref: str | None = None,
        pack_id: str | None = None,
        caller_app: str | None = None,
        tenant_id: str | None = None,
        workflow_surface: str | None = None,
        runtime_state: str | None = None,
        review_state: str | None = None,
        workflow_authority_owner: str | None = None,
        limit: int,
    ) -> list[WorkflowPackRunRecord]:
        statement = select(WorkflowPackRunModel)
        if registration_ref is not None:
            statement = statement.where(WorkflowPackRunModel.registration_ref == registration_ref)
        if pack_id is not None:
            statement = statement.where(WorkflowPackRunModel.pack_id == pack_id)
        if caller_app is not None:
            statement = statement.where(WorkflowPackRunModel.caller_app == caller_app)
        if tenant_id is not None:
            statement = statement.where(WorkflowPackRunModel.tenant_id == tenant_id)
        if workflow_surface is not None:
            statement = statement.where(WorkflowPackRunModel.workflow_surface == workflow_surface)
        if runtime_state is not None:
            statement = statement.where(WorkflowPackRunModel.runtime_state == runtime_state)
        if review_state is not None:
            statement = statement.where(WorkflowPackRunModel.review_state == review_state)
        if workflow_authority_owner is not None:
            statement = statement.where(
                WorkflowPackRunModel.workflow_authority_owner == workflow_authority_owner
            )
        statement = statement.order_by(WorkflowPackRunModel.created_at.desc()).limit(max(limit, 0))
        with self._session_factory() as session:
            models = session.scalars(statement).all()
            return [self._to_run_record(model) for model in models]

    def get_run(self, *, run_id: str) -> WorkflowPackRunRecord | None:
        with self._session_factory() as session:
            model = session.get(WorkflowPackRunModel, run_id)
            if model is None:
                return None
            return self._to_run_record(model)

    def save_run(self, record: WorkflowPackRunRecord) -> None:
        model = WorkflowPackRunModel(
            run_id=record.run_id,
            pack_id=record.pack_id,
            pack_family=record.pack_family,
            pack_version=record.pack_version,
            registration_ref=record.registration_ref,
            task_id=record.task_id,
            request_id=record.request_id,
            caller_app=record.caller_app,
            correlation_id=record.correlation_id,
            tenant_id=record.tenant_id,
            workflow_surface=record.workflow_surface,
            workflow_authority_owner=record.workflow_authority_owner,
            runtime_state=record.runtime_state,
            review_state=record.review_state,
            review_required=record.review_required,
            provider_mode=record.provider_mode,
            stubbed=record.stubbed,
            output_preview=record.output_preview,
            structured_output_keys=list(record.structured_output_keys),
            evidence_descriptors=[
                descriptor.model_dump(mode="json") for descriptor in record.evidence_descriptors
            ],
            artifact_refs=[artifact.model_dump(mode="json") for artifact in record.artifact_refs],
            supersedes_run_id=record.supersedes_run_id,
            superseded_by_run_id=record.superseded_by_run_id,
            created_at=record.created_at,
            completed_at=record.completed_at,
            last_updated_at=record.last_updated_at,
        )
        with self._session_factory() as session:
            session.merge(model)
            session.commit()

    def list_events(self, *, run_id: str) -> list[WorkflowPackRunEventRecord]:
        with self._session_factory() as session:
            models = session.scalars(
                select(WorkflowPackRunEventModel)
                .where(WorkflowPackRunEventModel.run_id == run_id)
                .order_by(WorkflowPackRunEventModel.recorded_at)
            ).all()
            return [self._to_event_record(model) for model in models]

    def save_event(self, record: WorkflowPackRunEventRecord) -> None:
        model = WorkflowPackRunEventModel(
            event_id=record.event_id,
            run_id=record.run_id,
            event_type=record.event_type,
            runtime_state=record.runtime_state,
            review_state=record.review_state,
            actor=record.actor,
            message=record.message,
            recorded_at=record.recorded_at,
        )
        with self._session_factory() as session:
            session.merge(model)
            session.commit()

    def _to_run_record(self, model: WorkflowPackRunModel) -> WorkflowPackRunRecord:
        return WorkflowPackRunRecord(
            run_id=model.run_id,
            pack_id=model.pack_id,
            pack_family=model.pack_family,
            pack_version=model.pack_version,
            registration_ref=model.registration_ref,
            task_id=model.task_id,
            request_id=model.request_id,
            caller_app=model.caller_app,
            correlation_id=model.correlation_id,
            tenant_id=model.tenant_id,
            workflow_surface=model.workflow_surface,
            workflow_authority_owner=model.workflow_authority_owner,
            runtime_state=model.runtime_state,
            review_state=model.review_state,
            review_required=model.review_required,
            provider_mode=model.provider_mode,
            stubbed=model.stubbed,
            output_preview=model.output_preview,
            structured_output_keys=list(model.structured_output_keys),
            evidence_descriptors=[
                ExecutionEvidenceDescriptor.model_validate(item)
                for item in model.evidence_descriptors
            ],
            artifact_refs=[ArtifactDescriptor.model_validate(item) for item in model.artifact_refs],
            supersedes_run_id=model.supersedes_run_id,
            superseded_by_run_id=model.superseded_by_run_id,
            created_at=model.created_at,
            completed_at=model.completed_at,
            last_updated_at=model.last_updated_at,
        )

    def _to_event_record(self, model: WorkflowPackRunEventModel) -> WorkflowPackRunEventRecord:
        return WorkflowPackRunEventRecord(
            event_id=model.event_id,
            run_id=model.run_id,
            event_type=model.event_type,
            runtime_state=model.runtime_state,
            review_state=model.review_state,
            actor=model.actor,
            message=model.message,
            recorded_at=model.recorded_at,
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
