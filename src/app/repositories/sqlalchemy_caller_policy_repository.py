from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.contracts.access_control import (
    CallerLifecycleStatus,
    CallerPolicyDescriptor,
    TenantPolicyMode,
)
from app.db.models import CallerPolicyModel
from app.repositories.sqlalchemy_repository_base import SqlAlchemyRepositoryBase


class SqlAlchemyCallerPolicyRepository(SqlAlchemyRepositoryBase):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._ensure_sqlite_parent_directory()
        self._configure_sqlalchemy(database_url)

    def list_policies(self) -> list[CallerPolicyDescriptor]:
        with self._session_factory() as session:
            models = session.scalars(
                select(CallerPolicyModel).order_by(CallerPolicyModel.caller_app)
            ).all()
            return [self._to_descriptor(model) for model in models]

    def get_policy(self, caller_app: str) -> CallerPolicyDescriptor | None:
        with self._session_factory() as session:
            model = session.get(CallerPolicyModel, caller_app)
            if model is None:
                return None
            return self._to_descriptor(model)

    def _to_descriptor(self, model: CallerPolicyModel) -> CallerPolicyDescriptor:
        return CallerPolicyDescriptor(
            caller_app=model.caller_app,
            lifecycle_status=CallerLifecycleStatus(model.lifecycle_status),
            description=model.description,
            allowed_task_ids=list(model.allowed_task_ids),
            allowed_retrieval_source_ids=list(model.allowed_retrieval_source_ids),
            allow_live_provider=model.allow_live_provider,
            allow_async_control=model.allow_async_control,
            allow_prompt_control=model.allow_prompt_control,
            allow_provider_control=model.allow_provider_control,
            allow_audit_read_all_tenants=model.allow_audit_read_all_tenants,
            tenant_policy_mode=TenantPolicyMode(model.tenant_policy_mode),
            restricted_tenant_ids=list(model.restricted_tenant_ids),
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
