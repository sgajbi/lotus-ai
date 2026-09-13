from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta

from pathlib import Path
from typing import Callable

from sqlalchemy import delete, select

from app.contracts.access_control import (
    AuthorizationCapabilityType,
    AuthorizationDecision,
    AuthorizationOutcome,
    TenantPolicyMode,
)
from app.db.models import (
    ArtifactMetadataModel,
    AsyncControlEventModel,
    AsyncJobAttemptModel,
    AsyncJobModel,
    AsyncWorkerLeaseModel,
)
from app.repositories.artifact_repository import ArtifactRecord
from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeClaimRecord,
    AsyncRuntimeClaimTransition,
    AsyncRuntimeControlEventRecord,
    AsyncRuntimeJobRecord,
    AsyncRuntimeLeaseRecord,
    AsyncRuntimeRecoveryTransition,
    AsyncRuntimeRepository,
)
from app.repositories.sqlalchemy_repository_base import SqlAlchemyRepositoryBase


class SqlAlchemyAsyncRuntimeRepository(SqlAlchemyRepositoryBase, AsyncRuntimeRepository):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._ensure_sqlite_parent_directory()
        self._configure_sqlalchemy(database_url)

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
            tenant_id=record.tenant_id,
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
            job_model = session.scalars(
                statement.order_by(AsyncJobModel.submitted_at).with_for_update(skip_locked=True)
            ).first()
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
            job_model = session.scalars(
                select(AsyncJobModel)
                .where(AsyncJobModel.job_id == job_id, AsyncJobModel.lifecycle_status == "QUEUED")
                .with_for_update(skip_locked=True)
            ).first()
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

    def transition_current_claim(
        self,
        *,
        job_id: str,
        worker_id: str,
        attempt_id: str,
        now: str | None,
        job_status: str | None,
        job_message: str | None,
        attempt_status: str | None,
        attempt_message: str,
        failure_reason: str | None,
        lease_expires_at: str | None,
        terminal_artifact: ArtifactRecord | None,
        next_attempt_message: str | None = None,
        now_factory: Callable[[], str] | None = None,
        lease_extension_seconds: int | None = None,
    ) -> AsyncRuntimeClaimTransition | None:
        """Apply one worker mutation only while its exact claim is current.

        The lease row is locked before its expiry and immutable attempt id are
        evaluated.  The dependent job and attempt writes share the same
        transaction, so a recovered worker cannot interleave a stale terminal
        write between an ownership read and a later merge/commit.
        """

        with self._session_factory() as session:
            lease_model = session.scalars(
                select(AsyncWorkerLeaseModel)
                .where(
                    AsyncWorkerLeaseModel.job_id == job_id,
                    AsyncWorkerLeaseModel.worker_id == worker_id,
                    AsyncWorkerLeaseModel.attempt_id == attempt_id,
                )
                .with_for_update()
            ).first()
            if lease_model is None:
                session.rollback()
                return None

            job_model = session.scalars(
                select(AsyncJobModel).where(AsyncJobModel.job_id == job_id).with_for_update()
            ).first()
            attempt_model = session.scalars(
                select(AsyncJobAttemptModel)
                .where(AsyncJobAttemptModel.attempt_id == attempt_id)
                .with_for_update()
            ).first()
            if (
                job_model is None
                or attempt_model is None
                or job_model.lifecycle_status not in {"CLAIMED", "RUNNING"}
                or attempt_model.job_id != job_id
            ):
                session.rollback()
                return None
            # Every row the transition mutates is locked before sampling time.
            # A transaction-start timestamp (or a sample made before a lock
            # wait) can otherwise admit a lease that expired while waiting.
            effective_now = now_factory() if now_factory is not None else now
            if effective_now is None:
                raise ValueError("A fresh claim-transition timestamp is required.")
            if lease_model.lease_expires_at <= effective_now:
                session.rollback()
                return None

            successor: AsyncRuntimeAttemptRecord | None = None
            if next_attempt_message is not None:
                next_attempt_number = job_model.attempt_count + 1
                successor = AsyncRuntimeAttemptRecord(
                    attempt_id=f"{job_model.job_id}_attempt_{next_attempt_number:03d}",
                    job_id=job_model.job_id,
                    attempt_number=next_attempt_number,
                    lifecycle_status="QUEUED",
                    worker_id=None,
                    claimed_at=None,
                    heartbeat_at=None,
                    started_at=None,
                    completed_at=None,
                    failure_reason=None,
                    recorded_message=next_attempt_message,
                )
                job_model.attempt_count = successor.attempt_number

            if job_status is not None:
                job_model.lifecycle_status = job_status
            if job_message is not None:
                job_model.latest_message = job_message
            if terminal_artifact is not None:
                job_model.artifact_ids = [*job_model.artifact_ids, terminal_artifact.artifact_id]
                session.add(self._artifact_metadata_model(terminal_artifact))

            if attempt_status is not None:
                attempt_model.lifecycle_status = attempt_status
            attempt_model.heartbeat_at = effective_now
            if attempt_status == "RUNNING" and attempt_model.started_at is None:
                attempt_model.started_at = effective_now
            if attempt_status in {"COMPLETED", "FAILED", "ABANDONED"}:
                attempt_model.completed_at = effective_now
            attempt_model.failure_reason = failure_reason
            attempt_model.recorded_message = attempt_message

            persisted_lease: AsyncRuntimeLeaseRecord | None
            if lease_expires_at is None and lease_extension_seconds is None:
                session.delete(lease_model)
                persisted_lease = None
            else:
                renewed_lease_expiry = (
                    _extend_lease(effective_now, lease_extension_seconds)
                    if lease_extension_seconds is not None
                    else lease_expires_at
                )
                assert renewed_lease_expiry is not None
                lease_model.heartbeat_at = effective_now
                lease_model.lease_expires_at = renewed_lease_expiry
                persisted_lease = self._to_lease_record(lease_model)

            if successor is not None:
                session.add(
                    AsyncJobAttemptModel(
                        attempt_id=successor.attempt_id,
                        job_id=successor.job_id,
                        attempt_number=successor.attempt_number,
                        lifecycle_status=successor.lifecycle_status,
                        worker_id=successor.worker_id,
                        claimed_at=successor.claimed_at,
                        heartbeat_at=successor.heartbeat_at,
                        started_at=successor.started_at,
                        completed_at=successor.completed_at,
                        failure_reason=successor.failure_reason,
                        recorded_message=successor.recorded_message,
                    )
                )
            session.commit()
            session.refresh(job_model)
            session.refresh(attempt_model)
            return AsyncRuntimeClaimTransition(
                job=self._to_job_record(job_model),
                attempt=self._to_attempt_record(attempt_model),
                lease=persisted_lease,
                next_attempt=successor,
            )

    def recover_expired_claim(
        self,
        *,
        job_id: str,
        recovered_at: str | None,
        next_attempt_message: str,
        now_factory: Callable[[], str] | None = None,
    ) -> AsyncRuntimeRecoveryTransition | None:
        """Recover precisely one expired lease generation in one transaction."""

        with self._session_factory() as session:
            lease_model = session.scalars(
                select(AsyncWorkerLeaseModel)
                .where(AsyncWorkerLeaseModel.job_id == job_id)
                .with_for_update()
            ).first()
            if lease_model is None:
                session.rollback()
                return None
            job_model = session.scalars(
                select(AsyncJobModel).where(AsyncJobModel.job_id == job_id).with_for_update()
            ).first()
            attempt_model = session.scalars(
                select(AsyncJobAttemptModel)
                .where(AsyncJobAttemptModel.attempt_id == lease_model.attempt_id)
                .with_for_update()
            ).first()
            if (
                job_model is None
                or attempt_model is None
                or job_model.lifecycle_status not in {"CLAIMED", "RUNNING"}
            ):
                session.rollback()
                return None
            # Recovery takes the same fresh-after-lock time boundary as every
            # worker claim mutation; a lock wait must not recover too early.
            effective_recovered_at = now_factory() if now_factory is not None else recovered_at
            if effective_recovered_at is None:
                raise ValueError("A fresh claim-recovery timestamp is required.")
            if lease_model.lease_expires_at > effective_recovered_at:
                session.rollback()
                return None

            next_attempt_number = job_model.attempt_count + 1
            next_attempt = AsyncRuntimeAttemptRecord(
                attempt_id=f"{job_model.job_id}_attempt_{next_attempt_number:03d}",
                job_id=job_model.job_id,
                attempt_number=next_attempt_number,
                lifecycle_status="QUEUED",
                worker_id=None,
                claimed_at=None,
                heartbeat_at=None,
                started_at=None,
                completed_at=None,
                failure_reason=None,
                recorded_message=next_attempt_message,
            )

            attempt_model.lifecycle_status = "ABANDONED"
            attempt_model.heartbeat_at = lease_model.heartbeat_at
            attempt_model.completed_at = effective_recovered_at
            attempt_model.failure_reason = "LEASE_EXPIRED"
            attempt_model.recorded_message = (
                "Attempt abandoned after lease expiry and queued for recovery."
            )
            job_model.lifecycle_status = "QUEUED"
            job_model.latest_message = next_attempt.recorded_message
            job_model.attempt_count = next_attempt.attempt_number
            session.add(
                AsyncJobAttemptModel(
                    attempt_id=next_attempt.attempt_id,
                    job_id=next_attempt.job_id,
                    attempt_number=next_attempt.attempt_number,
                    lifecycle_status=next_attempt.lifecycle_status,
                    worker_id=next_attempt.worker_id,
                    claimed_at=next_attempt.claimed_at,
                    heartbeat_at=next_attempt.heartbeat_at,
                    started_at=next_attempt.started_at,
                    completed_at=next_attempt.completed_at,
                    failure_reason=next_attempt.failure_reason,
                    recorded_message=next_attempt.recorded_message,
                )
            )
            session.delete(lease_model)
            session.commit()
            session.refresh(job_model)
            session.refresh(attempt_model)
            return AsyncRuntimeRecoveryTransition(
                job=self._to_job_record(job_model),
                abandoned_attempt=self._to_attempt_record(attempt_model),
                next_attempt=next_attempt,
            )

    def delete_job_records(self, job_ids: Sequence[str]) -> tuple[int, int, int]:
        if not job_ids:
            return 0, 0, 0
        ids = list(job_ids)
        with self._session_factory() as session:
            leases = session.execute(
                delete(AsyncWorkerLeaseModel).where(AsyncWorkerLeaseModel.job_id.in_(ids))
            )
            attempts = session.execute(
                delete(AsyncJobAttemptModel).where(AsyncJobAttemptModel.job_id.in_(ids))
            )
            jobs = session.execute(delete(AsyncJobModel).where(AsyncJobModel.job_id.in_(ids)))
            session.commit()
            return (
                int(getattr(jobs, "rowcount", 0) or 0),
                int(getattr(attempts, "rowcount", 0) or 0),
                int(getattr(leases, "rowcount", 0) or 0),
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

    def delete_control_events(self, event_ids: Sequence[str]) -> int:
        if not event_ids:
            return 0
        with self._session_factory() as session:
            result = session.execute(
                delete(AsyncControlEventModel).where(
                    AsyncControlEventModel.event_id.in_(list(event_ids))
                )
            )
            session.commit()
            return int(getattr(result, "rowcount", 0) or 0)

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
            tenant_id=model.tenant_id,
        )

    @staticmethod
    def _artifact_metadata_model(record: ArtifactRecord) -> ArtifactMetadataModel:
        return ArtifactMetadataModel(
            artifact_id=record.artifact_id,
            domain=record.domain,
            artifact_type=record.artifact_type,
            source_object_kind=record.source_object_kind,
            source_object_id=record.source_object_id,
            lifecycle_status=record.lifecycle_status.value,
            retention_posture=record.retention_posture,
            media_type=record.media_type,
            byte_size=record.byte_size,
            checksum_sha256=record.checksum_sha256,
            storage_backend=record.storage_backend.value,
            storage_reference=record.storage_reference,
            lineage_parent_artifact_id=record.lineage_parent_artifact_id,
            superseded_by_artifact_id=record.superseded_by_artifact_id,
            created_at=record.created_at,
            created_by=record.created_by,
            tenant_id=record.tenant_id,
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


def _extend_lease(now: str, seconds: int) -> str:
    return (
        (datetime.fromisoformat(now.replace("Z", "+00:00")) + timedelta(seconds=seconds))
        .isoformat()
        .replace("+00:00", "Z")
    )
