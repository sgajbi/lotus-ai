from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.contracts.artifacts import ArtifactDescriptor
from app.contracts.workflow_pack_queue_policies import (
    WorkflowPackQueueLane,
    WorkflowPackQueueState,
)
from app.db.models import (
    WorkflowPackAdmissionGuardModel,
    WorkflowPackAdmissionLeaseModel,
)
from app.repositories.workflow_pack_admission_lease_repository import (
    WorkflowPackAdmissionAttempt,
)
from app.services.workflow_pack_queue_admission_models import (
    WorkflowPackQueueAdmissionLease,
)


class SqlAlchemyWorkflowPackAdmissionLeaseRepository:
    """Replica-shared admission leases.

    Capacity decisions serialize per policy through a guard row locked FOR
    UPDATE (the provider-operations counter pattern): concurrent try_admit
    calls for one policy queue on the guard, so count-and-insert is atomic
    even from separate processes.
    """

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._ensure_sqlite_parent_directory()
        self._engine = create_engine(database_url)
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)

    def try_admit(
        self,
        lease: WorkflowPackQueueAdmissionLease,
        *,
        pack_limit: int,
        lane_limit: int,
    ) -> WorkflowPackAdmissionAttempt:
        with self._session_factory() as session:
            self._lock_policy_guard(session, policy_id=lease.policy_id)
            pack_count = session.execute(
                select(func.count())
                .select_from(WorkflowPackAdmissionLeaseModel)
                .where(WorkflowPackAdmissionLeaseModel.policy_id == lease.policy_id)
            ).scalar_one()
            lane_count = session.execute(
                select(func.count())
                .select_from(WorkflowPackAdmissionLeaseModel)
                .where(
                    WorkflowPackAdmissionLeaseModel.policy_id == lease.policy_id,
                    WorkflowPackAdmissionLeaseModel.lane == lease.lane.value,
                )
            ).scalar_one()
            if pack_count >= pack_limit or lane_count >= lane_limit:
                session.rollback()
                return WorkflowPackAdmissionAttempt(
                    admitted=False,
                    active_pack_count=pack_count,
                    active_lane_count=lane_count,
                )
            session.add(self._to_model(lease))
            session.commit()
            return WorkflowPackAdmissionAttempt(
                admitted=True,
                active_pack_count=pack_count,
                active_lane_count=lane_count,
            )

    def get_lease(self, queue_item_id: str) -> WorkflowPackQueueAdmissionLease | None:
        with self._session_factory() as session:
            model = session.get(WorkflowPackAdmissionLeaseModel, queue_item_id)
            if model is None:
                return None
            return self._to_lease(model)

    def delete_lease(self, queue_item_id: str) -> None:
        with self._session_factory() as session:
            model = session.get(WorkflowPackAdmissionLeaseModel, queue_item_id)
            if model is not None:
                session.delete(model)
                session.commit()

    def list_leases(self) -> list[WorkflowPackQueueAdmissionLease]:
        with self._session_factory() as session:
            models = (
                session.execute(
                    select(WorkflowPackAdmissionLeaseModel).order_by(
                        WorkflowPackAdmissionLeaseModel.admitted_at
                    )
                )
                .scalars()
                .all()
            )
            return [self._to_lease(model) for model in models]

    def clear(self) -> None:
        with self._session_factory() as session:
            for model in session.execute(select(WorkflowPackAdmissionLeaseModel)).scalars():
                session.delete(model)
            session.commit()

    def _lock_policy_guard(self, session: Session, *, policy_id: str) -> None:
        guard = session.execute(
            select(WorkflowPackAdmissionGuardModel)
            .where(WorkflowPackAdmissionGuardModel.policy_id == policy_id)
            .with_for_update()
        ).scalar_one_or_none()
        if guard is None:
            session.add(WorkflowPackAdmissionGuardModel(policy_id=policy_id))
            session.flush()
            session.execute(
                select(WorkflowPackAdmissionGuardModel)
                .where(WorkflowPackAdmissionGuardModel.policy_id == policy_id)
                .with_for_update()
            ).scalar_one()

    def _to_model(self, lease: WorkflowPackQueueAdmissionLease) -> WorkflowPackAdmissionLeaseModel:
        return WorkflowPackAdmissionLeaseModel(
            queue_item_id=lease.queue_item_id,
            policy_id=lease.policy_id,
            workflow_pack_id=lease.workflow_pack_id,
            workflow_pack_version=lease.workflow_pack_version,
            lane=lease.lane.value,
            state=lease.state.value,
            admitted_at=lease.admitted_at,
            caller_app=lease.caller_app,
            correlation_id=lease.correlation_id,
            tenant_id=lease.tenant_id,
            workflow_surface=lease.workflow_surface,
            artifact_refs_payload=[
                artifact.model_dump(mode="json") for artifact in lease.artifact_refs
            ],
        )

    def _to_lease(self, model: WorkflowPackAdmissionLeaseModel) -> WorkflowPackQueueAdmissionLease:
        return WorkflowPackQueueAdmissionLease(
            queue_item_id=model.queue_item_id,
            policy_id=model.policy_id,
            workflow_pack_id=model.workflow_pack_id,
            workflow_pack_version=model.workflow_pack_version,
            lane=WorkflowPackQueueLane(model.lane),
            state=WorkflowPackQueueState(model.state),
            admitted_at=model.admitted_at,
            caller_app=model.caller_app,
            correlation_id=model.correlation_id,
            tenant_id=model.tenant_id,
            workflow_surface=model.workflow_surface,
            artifact_refs=tuple(
                ArtifactDescriptor.model_validate(item) for item in model.artifact_refs_payload
            ),
        )

    def _ensure_sqlite_parent_directory(self) -> None:
        prefix = "sqlite:///"
        if not self._database_url.startswith(prefix):
            return
        raw_path = self._database_url.removeprefix(prefix)
        if raw_path == ":memory:":
            return
        Path(raw_path).parent.mkdir(parents=True, exist_ok=True)
