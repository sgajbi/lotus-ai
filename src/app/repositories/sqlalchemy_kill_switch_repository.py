from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.contracts.kill_switches import (
    KillSwitchActivationRecord,
    KillSwitchScope,
    KillSwitchSemantics,
)
from app.db.models import KillSwitchActivationModel
from app.repositories.sqlalchemy_repository_base import SqlAlchemyRepositoryBase


class SqlAlchemyKillSwitchRepository(SqlAlchemyRepositoryBase):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._ensure_sqlite_parent_directory()
        self._configure_sqlalchemy(database_url)

    def list_activations(self) -> list[KillSwitchActivationRecord]:
        with self._session_factory() as session:
            models = session.scalars(
                select(KillSwitchActivationModel).order_by(
                    KillSwitchActivationModel.activated_at.desc()
                )
            ).all()
            return [self._to_record(model) for model in models]

    def get_activation(self, switch_id: str) -> KillSwitchActivationRecord | None:
        with self._session_factory() as session:
            model = session.get(KillSwitchActivationModel, switch_id)
            if model is None:
                return None
            return self._to_record(model)

    def upsert_activation(self, activation: KillSwitchActivationRecord) -> None:
        with self._session_factory() as session:
            model = session.get(KillSwitchActivationModel, activation.switch_id)
            if model is None:
                model = KillSwitchActivationModel(switch_id=activation.switch_id)
                session.add(model)
            model.scope = activation.scope.value
            model.semantics = activation.semantics.value
            model.target = activation.target
            model.reason = activation.reason
            model.requested_by = activation.requested_by
            model.approved_by = activation.approved_by
            model.activated_at = activation.activated_at
            model.expires_at_utc = activation.expires_at_utc
            model.expiry_recorded_at = activation.expiry_recorded_at
            model.cleared_at = activation.cleared_at
            model.cleared_by = activation.cleared_by
            model.clear_reason = activation.clear_reason
            session.commit()

    def _to_record(self, model: KillSwitchActivationModel) -> KillSwitchActivationRecord:
        return KillSwitchActivationRecord(
            switch_id=model.switch_id,
            scope=KillSwitchScope(model.scope),
            semantics=KillSwitchSemantics(model.semantics),
            target=model.target,
            reason=model.reason,
            requested_by=model.requested_by,
            approved_by=model.approved_by,
            activated_at=model.activated_at,
            expires_at_utc=model.expires_at_utc,
            expiry_recorded_at=model.expiry_recorded_at,
            cleared_at=model.cleared_at,
            cleared_by=model.cleared_by,
            clear_reason=model.clear_reason,
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
