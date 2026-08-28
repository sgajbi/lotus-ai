from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models import WorkflowPackExecutionIdempotencyModel
from app.repositories.sqlalchemy_repository_base import SqlAlchemyRepositoryBase
from app.workflow_pack_execution_idempotency.repository import (
    WorkflowPackExecutionIdempotencyConflictError,
    WorkflowPackExecutionIdempotencyOwnershipError,
    WorkflowPackExecutionIdempotencyRecord,
    WorkflowPackExecutionIdempotencyState,
    WorkflowPackExecutionReservation,
)


class SqlAlchemyWorkflowPackExecutionIdempotencyRepository(SqlAlchemyRepositoryBase):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        if database_url.startswith("sqlite"):
            database_path = database_url.split("///", maxsplit=1)[-1]
            if database_path and database_path != ":memory:":
                Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self._configure_sqlalchemy(database_url)

    def reserve(
        self, record: WorkflowPackExecutionIdempotencyRecord
    ) -> WorkflowPackExecutionReservation:
        with self._session_factory() as session:
            session.add(_to_model(record))
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                existing = self.get(record_id=record.record_id)
                if existing is None:
                    raise
                if existing.request_fingerprint != record.request_fingerprint:
                    raise WorkflowPackExecutionIdempotencyConflictError(
                        "idempotency key was reused with different workflow-pack execution input"
                    ) from exc
                return WorkflowPackExecutionReservation(record=existing, acquired=False)
        return WorkflowPackExecutionReservation(record=record, acquired=True)

    def get(self, *, record_id: str) -> WorkflowPackExecutionIdempotencyRecord | None:
        with self._session_factory() as session:
            model = session.scalar(
                select(WorkflowPackExecutionIdempotencyModel).where(
                    WorkflowPackExecutionIdempotencyModel.record_id == record_id
                )
            )
            return _to_record(model) if model is not None else None

    def complete(
        self,
        *,
        record_id: str,
        owner_token: str,
        response_payload: dict[str, object],
        updated_at: str,
    ) -> WorkflowPackExecutionIdempotencyRecord:
        return self._transition_owned_record(
            record_id=record_id,
            owner_token=owner_token,
            state=WorkflowPackExecutionIdempotencyState.COMPLETED,
            response_payload=response_payload,
            failure_code=None,
            updated_at=updated_at,
        )

    def mark_indeterminate(
        self,
        *,
        record_id: str,
        owner_token: str,
        failure_code: str,
        updated_at: str,
    ) -> WorkflowPackExecutionIdempotencyRecord:
        return self._transition_owned_record(
            record_id=record_id,
            owner_token=owner_token,
            state=WorkflowPackExecutionIdempotencyState.INDETERMINATE,
            response_payload=None,
            failure_code=failure_code,
            updated_at=updated_at,
        )

    def _transition_owned_record(
        self,
        *,
        record_id: str,
        owner_token: str,
        state: WorkflowPackExecutionIdempotencyState,
        response_payload: dict[str, object] | None,
        failure_code: str | None,
        updated_at: str,
    ) -> WorkflowPackExecutionIdempotencyRecord:
        with self._session_factory() as session:
            model = session.get(WorkflowPackExecutionIdempotencyModel, record_id)
            if (
                model is None
                or model.owner_token != owner_token
                or model.state != WorkflowPackExecutionIdempotencyState.IN_PROGRESS.value
            ):
                raise WorkflowPackExecutionIdempotencyOwnershipError(
                    "workflow-pack execution reservation is not owned by this execution"
                )
            model.state = state.value
            model.response_payload = response_payload
            model.failure_code = failure_code
            model.updated_at = updated_at
            session.commit()
            session.refresh(model)
            return _to_record(model)


def _to_model(
    record: WorkflowPackExecutionIdempotencyRecord,
) -> WorkflowPackExecutionIdempotencyModel:
    return WorkflowPackExecutionIdempotencyModel(
        record_id=record.record_id,
        caller_app=record.caller_app,
        tenant_scope=record.tenant_scope,
        idempotency_key=record.idempotency_key,
        request_fingerprint=record.request_fingerprint,
        state=record.state.value,
        owner_token=record.owner_token,
        response_payload=record.response_payload,
        failure_code=record.failure_code,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _to_record(
    model: WorkflowPackExecutionIdempotencyModel,
) -> WorkflowPackExecutionIdempotencyRecord:
    return WorkflowPackExecutionIdempotencyRecord(
        record_id=model.record_id,
        caller_app=model.caller_app,
        tenant_scope=model.tenant_scope,
        idempotency_key=model.idempotency_key,
        request_fingerprint=model.request_fingerprint,
        state=WorkflowPackExecutionIdempotencyState(model.state),
        owner_token=model.owner_token,
        response_payload=model.response_payload,
        failure_code=model.failure_code,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
