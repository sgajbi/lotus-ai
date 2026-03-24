from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker

from app.contracts.access_control import (
    AuthorizationCapabilityType,
    AuthorizationDecision,
    AuthorizationOutcome,
    TenantPolicyMode,
)
from app.db.models import (
    AsyncControlEventModel,
    AsyncJobAttemptModel,
    AsyncJobModel,
    AsyncWorkerLeaseModel,
)
from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeClaimRecord,
    AsyncRuntimeControlEventRecord,
    AsyncRuntimeJobRecord,
    AsyncRuntimeLeaseRecord,
    AsyncRuntimeRepository,
)


class SqlAlchemyAsyncRuntimeRepository(AsyncRuntimeRepository):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._ensure_sqlite_parent_directory()
        self._engine = create_engine(database_url, future=True)
        self._session_factory = sessionmaker(bind=self._engine, autoflush=False, future=True)

    def list_jobs(self) -> list[AsyncRuntimeJobRecord]:
        with self._session_factory() as session:
            models = session.scalars(
                select(AsyncJobModel).order_by(AsyncJobModel.submitted_at)
            ).all()
            return [self._to_job_record(model) for model in models]

    def get_job(self, *, job_id: str) -> AsyncRuntimeJobRecord | None:
        with self._session_factory() as session:
            model = session.get(AsyncJobModel, job_id)
            if model is None:
                return None
            return self._to_job_record(model)

    def save_job(self, record: AsyncRuntimeJobRecord) -> None:
        model = AsyncJobModel(
            job_id=record.job_id,
            job_type=record.job_type,
            target_id=record.target_id,
            lifecycle_status=record.lifecycle_status,
            submitted_at=record.submitted_at,
            caller_app=record.caller_app,
            correlation_id=record.correlation_id,
            payload_summary=record.payload_summary,
            execution_path=record.execution_path,
            related_evaluation_run_id=record.related_evaluation_run_id,
            latest_message=record.latest_message,
            attempt_count=record.attempt_count,
            artifact_ids=record.artifact_ids,
        )
        with self._session_factory() as session:
            session.merge(model)
            session.commit()

    def list_attempts(self, *, job_id: str) -> list[AsyncRuntimeAttemptRecord]:
        with self._session_factory() as session:
            models = session.scalars(
                select(AsyncJobAttemptModel)
                .where(AsyncJobAttemptModel.job_id == job_id)
                .order_by(AsyncJobAttemptModel.attempt_number)
            ).all()
            return [self._to_attempt_record(model) for model in models]

    def save_attempt(self, record: AsyncRuntimeAttemptRecord) -> None:
        model = AsyncJobAttemptModel(
            attempt_id=record.attempt_id,
            job_id=record.job_id,
            attempt_number=record.attempt_number,
            lifecycle_status=record.lifecycle_status,
            worker_id=record.worker_id,
            claimed_at=record.claimed_at,
            heartbeat_at=record.heartbeat_at,
            started_at=record.started_at,
            completed_at=record.completed_at,
            failure_reason=record.failure_reason,
            recorded_message=record.recorded_message,
        )
        with self._session_factory() as session:
            session.merge(model)
            session.commit()

    def get_attempt(self, *, attempt_id: str) -> AsyncRuntimeAttemptRecord | None:
        with self._session_factory() as session:
            model = session.get(AsyncJobAttemptModel, attempt_id)
            if model is None:
                return None
            return self._to_attempt_record(model)

    def list_leases(self) -> list[AsyncRuntimeLeaseRecord]:
        with self._session_factory() as session:
            models = session.scalars(
                select(AsyncWorkerLeaseModel).order_by(AsyncWorkerLeaseModel.claimed_at)
            ).all()
            return [self._to_lease_record(model) for model in models]

    def get_active_lease(self, *, job_id: str) -> AsyncRuntimeLeaseRecord | None:
        with self._session_factory() as session:
            model = session.scalars(
                select(AsyncWorkerLeaseModel).where(AsyncWorkerLeaseModel.job_id == job_id)
            ).first()
            if model is None:
                return None
            return self._to_lease_record(model)

    def save_lease(self, record: AsyncRuntimeLeaseRecord) -> None:
        model = AsyncWorkerLeaseModel(
            lease_id=record.lease_id,
            job_id=record.job_id,
            attempt_id=record.attempt_id,
            worker_id=record.worker_id,
            claimed_at=record.claimed_at,
            heartbeat_at=record.heartbeat_at,
            lease_expires_at=record.lease_expires_at,
        )
        with self._session_factory() as session:
            session.merge(model)
            session.commit()

    def delete_lease(self, *, lease_id: str) -> int:
        with self._session_factory() as session:
            result = session.execute(
                delete(AsyncWorkerLeaseModel).where(AsyncWorkerLeaseModel.lease_id == lease_id)
            )
            session.commit()
            return int(getattr(result, "rowcount", 0) or 0)

    def claim_next_runnable_job(
        self,
        *,
        worker_id: str,
        job_types: tuple[str, ...] | None,
        claimed_at: str,
        heartbeat_at: str,
        lease_expires_at: str,
        latest_message: str,
        attempt_message: str,
    ) -> AsyncRuntimeClaimRecord | None:
        with self._session_factory() as session:
            statement = select(AsyncJobModel).where(AsyncJobModel.lifecycle_status == "QUEUED")
            if job_types is not None:
                statement = statement.where(AsyncJobModel.job_type.in_(job_types))
            job_model = session.scalars(statement.order_by(AsyncJobModel.submitted_at)).first()
            if job_model is None:
                return None

            existing_lease = session.scalars(
                select(AsyncWorkerLeaseModel).where(
                    AsyncWorkerLeaseModel.job_id == job_model.job_id
                )
            ).first()
            if existing_lease is not None:
                return None

            attempt_model = session.scalars(
                select(AsyncJobAttemptModel)
                .where(AsyncJobAttemptModel.job_id == job_model.job_id)
                .order_by(AsyncJobAttemptModel.attempt_number.desc())
            ).first()
            if attempt_model is None:
                return None

            job_model.lifecycle_status = "CLAIMED"
            job_model.latest_message = latest_message
            attempt_model.lifecycle_status = "CLAIMED"
            attempt_model.worker_id = worker_id
            attempt_model.claimed_at = claimed_at
            attempt_model.heartbeat_at = heartbeat_at
            attempt_model.recorded_message = attempt_message

            lease_model = AsyncWorkerLeaseModel(
                lease_id=f"{job_model.job_id}_lease_{attempt_model.attempt_number:03d}",
                job_id=job_model.job_id,
                attempt_id=attempt_model.attempt_id,
                worker_id=worker_id,
                claimed_at=claimed_at,
                heartbeat_at=heartbeat_at,
                lease_expires_at=lease_expires_at,
            )
            session.add(lease_model)
            session.commit()
            session.refresh(job_model)
            session.refresh(attempt_model)
            session.refresh(lease_model)
            return AsyncRuntimeClaimRecord(
                job=self._to_job_record(job_model),
                attempt=self._to_attempt_record(attempt_model),
                lease=self._to_lease_record(lease_model),
            )

    def claim_runnable_job_by_id(
        self,
        *,
        job_id: str,
        worker_id: str,
        claimed_at: str,
        heartbeat_at: str,
        lease_expires_at: str,
        latest_message: str,
        attempt_message: str,
    ) -> AsyncRuntimeClaimRecord | None:
        with self._session_factory() as session:
            job_model = session.get(AsyncJobModel, job_id)
            if job_model is None or job_model.lifecycle_status != "QUEUED":
                return None

            existing_lease = session.scalars(
                select(AsyncWorkerLeaseModel).where(
                    AsyncWorkerLeaseModel.job_id == job_model.job_id
                )
            ).first()
            if existing_lease is not None:
                return None

            attempt_model = session.scalars(
                select(AsyncJobAttemptModel)
                .where(AsyncJobAttemptModel.job_id == job_model.job_id)
                .order_by(AsyncJobAttemptModel.attempt_number.desc())
            ).first()
            if attempt_model is None:
                return None

            job_model.lifecycle_status = "CLAIMED"
            job_model.latest_message = latest_message
            attempt_model.lifecycle_status = "CLAIMED"
            attempt_model.worker_id = worker_id
            attempt_model.claimed_at = claimed_at
            attempt_model.heartbeat_at = heartbeat_at
            attempt_model.recorded_message = attempt_message

            lease_model = AsyncWorkerLeaseModel(
                lease_id=f"{job_model.job_id}_lease_{attempt_model.attempt_number:03d}",
                job_id=job_model.job_id,
                attempt_id=attempt_model.attempt_id,
                worker_id=worker_id,
                claimed_at=claimed_at,
                heartbeat_at=heartbeat_at,
                lease_expires_at=lease_expires_at,
            )
            session.add(lease_model)
            session.commit()
            session.refresh(job_model)
            session.refresh(attempt_model)
            session.refresh(lease_model)
            return AsyncRuntimeClaimRecord(
                job=self._to_job_record(job_model),
                attempt=self._to_attempt_record(attempt_model),
                lease=self._to_lease_record(lease_model),
            )

    def list_control_events(
        self, *, limit: int = 20, job_id: str | None = None
    ) -> list[AsyncRuntimeControlEventRecord]:
        with self._session_factory() as session:
            statement = select(AsyncControlEventModel)
            if job_id is not None:
                statement = statement.where(AsyncControlEventModel.job_id == job_id)
            models = session.scalars(
                statement.order_by(AsyncControlEventModel.recorded_at.desc()).limit(max(limit, 1))
            ).all()
            return [self._to_control_event_record(model) for model in models]

    def save_control_event(self, record: AsyncRuntimeControlEventRecord) -> None:
        model = AsyncControlEventModel(
            event_id=record.event_id,
            job_id=record.job_id,
            action_type=record.action_type,
            requested_by=record.requested_by,
            approved_by=record.approved_by,
            reason=record.reason,
            prior_status=record.prior_status,
            resulting_status=record.resulting_status,
            affected_attempt_id=record.affected_attempt_id,
            authorization_payload=record.authorization.model_dump(mode="json"),
            recorded_at=record.recorded_at,
        )
        with self._session_factory() as session:
            session.merge(model)
            session.commit()

    def _to_job_record(self, model: AsyncJobModel) -> AsyncRuntimeJobRecord:
        return AsyncRuntimeJobRecord(
            job_id=model.job_id,
            job_type=model.job_type,
            target_id=model.target_id,
            lifecycle_status=model.lifecycle_status,
            submitted_at=model.submitted_at,
            caller_app=model.caller_app,
            correlation_id=model.correlation_id,
            payload_summary=model.payload_summary,
            execution_path=model.execution_path,
            related_evaluation_run_id=model.related_evaluation_run_id,
            latest_message=model.latest_message,
            attempt_count=model.attempt_count,
            artifact_ids=list(model.artifact_ids),
        )

    def _to_attempt_record(self, model: AsyncJobAttemptModel) -> AsyncRuntimeAttemptRecord:
        return AsyncRuntimeAttemptRecord(
            attempt_id=model.attempt_id,
            job_id=model.job_id,
            attempt_number=model.attempt_number,
            lifecycle_status=model.lifecycle_status,
            worker_id=model.worker_id,
            claimed_at=model.claimed_at,
            heartbeat_at=model.heartbeat_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
            failure_reason=model.failure_reason,
            recorded_message=model.recorded_message,
        )

    def _to_lease_record(self, model: AsyncWorkerLeaseModel) -> AsyncRuntimeLeaseRecord:
        return AsyncRuntimeLeaseRecord(
            lease_id=model.lease_id,
            job_id=model.job_id,
            attempt_id=model.attempt_id,
            worker_id=model.worker_id,
            claimed_at=model.claimed_at,
            heartbeat_at=model.heartbeat_at,
            lease_expires_at=model.lease_expires_at,
        )

    def _to_control_event_record(
        self, model: AsyncControlEventModel
    ) -> AsyncRuntimeControlEventRecord:
        return AsyncRuntimeControlEventRecord(
            event_id=model.event_id,
            job_id=model.job_id,
            action_type=model.action_type,
            requested_by=model.requested_by,
            approved_by=model.approved_by,
            reason=model.reason,
            prior_status=model.prior_status,
            resulting_status=model.resulting_status,
            affected_attempt_id=model.affected_attempt_id,
            authorization=(
                AuthorizationDecision.model_validate(model.authorization_payload)
                if model.authorization_payload is not None
                else _build_legacy_control_authorization()
            ),
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


def _build_legacy_control_authorization() -> AuthorizationDecision:
    return AuthorizationDecision(
        caller_app="legacy-control-plane",
        capability_type=AuthorizationCapabilityType.ASYNC_CONTROL,
        outcome=AuthorizationOutcome.ALLOWED,
        allowed=True,
        tenant_policy_mode=TenantPolicyMode.OPTIONAL,
        task_id=None,
        requested_source_ids=[],
        effective_source_ids=[],
        tenant_id=None,
        summary=(
            "Legacy async control event predates explicit caller-authorization capture and is "
            "treated as a durable pre-RFC-0012 operator action."
        ),
    )
