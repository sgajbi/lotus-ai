from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import sessionmaker

from app.contracts.providers import ProviderFailureCategory, ProviderQuotaScope
from app.db.models import (
    ProviderBudgetStateModel,
    ProviderDegradationStateModel,
    ProviderQuotaStateModel,
)
from app.repositories.provider_operations_repository import (
    ProviderBudgetStateRecord,
    ProviderDegradationStateRecord,
    ProviderOperationsRepository,
    ProviderQuotaStateRecord,
)


class SqlAlchemyProviderOperationsRepository(ProviderOperationsRepository):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._ensure_sqlite_parent_directory()
        self._engine = create_engine(database_url, future=True)
        self._session_factory = sessionmaker(bind=self._engine, autoflush=False, future=True)

    def list_quota_states(self) -> list[ProviderQuotaStateRecord]:
        with self._session_factory() as session:
            models = session.scalars(
                select(ProviderQuotaStateModel).order_by(
                    ProviderQuotaStateModel.scope,
                    ProviderQuotaStateModel.scope_key,
                )
            ).all()
            return [self._to_quota_record(model) for model in models]

    def get_quota_state(
        self,
        *,
        scope: ProviderQuotaScope,
        scope_key: str,
    ) -> ProviderQuotaStateRecord | None:
        with self._session_factory() as session:
            model = session.get(ProviderQuotaStateModel, (scope.value, scope_key))
            if model is None:
                return None
            return self._to_quota_record(model)

    def save_quota_state(self, record: ProviderQuotaStateRecord) -> None:
        model = ProviderQuotaStateModel(
            scope=record.scope.value,
            scope_key=record.scope_key,
            request_count=record.request_count,
            updated_at=record.updated_at,
        )
        with self._session_factory() as session:
            session.merge(model)
            session.commit()

    def increment_quota_state(
        self,
        *,
        scope: ProviderQuotaScope,
        scope_key: str,
        amount: int,
        updated_at: str,
    ) -> ProviderQuotaStateRecord:
        with self._session_factory() as session:
            statement = sqlite_insert(ProviderQuotaStateModel).values(
                scope=scope.value,
                scope_key=scope_key,
                request_count=amount,
                updated_at=updated_at,
            )
            statement = statement.on_conflict_do_update(
                index_elements=[
                    ProviderQuotaStateModel.scope,
                    ProviderQuotaStateModel.scope_key,
                ],
                set_={
                    "request_count": ProviderQuotaStateModel.request_count + amount,
                    "updated_at": updated_at,
                },
            )
            session.execute(statement)
            session.commit()

        record = self.get_quota_state(scope=scope, scope_key=scope_key)
        if record is None:
            raise RuntimeError("Failed to load incremented provider quota state.")
        return record

    def get_budget_state(self, *, budget_key: str) -> ProviderBudgetStateRecord | None:
        with self._session_factory() as session:
            model = session.get(ProviderBudgetStateModel, budget_key)
            if model is None:
                return None
            return self._to_budget_record(model)

    def save_budget_state(self, record: ProviderBudgetStateRecord) -> None:
        model = ProviderBudgetStateModel(
            budget_key=record.budget_key,
            current_spend_usd=record.current_spend_usd,
            updated_at=record.updated_at,
        )
        with self._session_factory() as session:
            session.merge(model)
            session.commit()

    def add_budget_spend(
        self,
        *,
        budget_key: str,
        amount_usd: float,
        updated_at: str,
    ) -> ProviderBudgetStateRecord:
        with self._session_factory() as session:
            statement = sqlite_insert(ProviderBudgetStateModel).values(
                budget_key=budget_key,
                current_spend_usd=amount_usd,
                updated_at=updated_at,
            )
            statement = statement.on_conflict_do_update(
                index_elements=[ProviderBudgetStateModel.budget_key],
                set_={
                    "current_spend_usd": ProviderBudgetStateModel.current_spend_usd + amount_usd,
                    "updated_at": updated_at,
                },
            )
            session.execute(statement)
            session.commit()

        record = self.get_budget_state(budget_key=budget_key)
        if record is None:
            raise RuntimeError("Failed to load incremented provider budget state.")
        return record

    def get_degradation_state(
        self,
        *,
        degradation_key: str,
    ) -> ProviderDegradationStateRecord | None:
        with self._session_factory() as session:
            model = session.get(ProviderDegradationStateModel, degradation_key)
            if model is None:
                return None
            return self._to_degradation_record(model)

    def save_degradation_state(self, record: ProviderDegradationStateRecord) -> None:
        model = ProviderDegradationStateModel(
            degradation_key=record.degradation_key,
            consecutive_failure_count=record.consecutive_failure_count,
            last_failure_category=(
                record.last_failure_category.value
                if record.last_failure_category is not None
                else None
            ),
            circuit_open_until=record.circuit_open_until,
            timeout_failure_count=record.timeout_failure_count,
            rate_limited_failure_count=record.rate_limited_failure_count,
            upstream_error_failure_count=record.upstream_error_failure_count,
            updated_at=record.updated_at,
        )
        with self._session_factory() as session:
            session.merge(model)
            session.commit()

    def record_degradation_failure(
        self,
        *,
        degradation_key: str,
        category: ProviderFailureCategory,
        updated_at: str,
    ) -> ProviderDegradationStateRecord:
        with self._session_factory() as session:
            statement = sqlite_insert(ProviderDegradationStateModel).values(
                degradation_key=degradation_key,
                consecutive_failure_count=1,
                last_failure_category=category.value,
                circuit_open_until=None,
                timeout_failure_count=int(category == ProviderFailureCategory.PROVIDER_TIMEOUT),
                rate_limited_failure_count=int(
                    category == ProviderFailureCategory.PROVIDER_RATE_LIMITED
                ),
                upstream_error_failure_count=int(
                    category == ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR
                ),
                updated_at=updated_at,
            )
            statement = statement.on_conflict_do_update(
                index_elements=[ProviderDegradationStateModel.degradation_key],
                set_={
                    "consecutive_failure_count": ProviderDegradationStateModel.consecutive_failure_count
                    + 1,
                    "last_failure_category": category.value,
                    "timeout_failure_count": ProviderDegradationStateModel.timeout_failure_count
                    + int(category == ProviderFailureCategory.PROVIDER_TIMEOUT),
                    "rate_limited_failure_count": ProviderDegradationStateModel.rate_limited_failure_count
                    + int(category == ProviderFailureCategory.PROVIDER_RATE_LIMITED),
                    "upstream_error_failure_count": ProviderDegradationStateModel.upstream_error_failure_count
                    + int(category == ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR),
                    "updated_at": updated_at,
                },
            )
            session.execute(statement)
            session.commit()

        record = self.get_degradation_state(degradation_key=degradation_key)
        if record is None:
            raise RuntimeError("Failed to load incremented provider degradation state.")
        return record

    def _to_quota_record(self, model: ProviderQuotaStateModel) -> ProviderQuotaStateRecord:
        return ProviderQuotaStateRecord(
            scope=ProviderQuotaScope(model.scope),
            scope_key=model.scope_key,
            request_count=model.request_count,
            updated_at=model.updated_at,
        )

    def _to_budget_record(self, model: ProviderBudgetStateModel) -> ProviderBudgetStateRecord:
        return ProviderBudgetStateRecord(
            budget_key=model.budget_key,
            current_spend_usd=model.current_spend_usd,
            updated_at=model.updated_at,
        )

    def _to_degradation_record(
        self,
        model: ProviderDegradationStateModel,
    ) -> ProviderDegradationStateRecord:
        return ProviderDegradationStateRecord(
            degradation_key=model.degradation_key,
            consecutive_failure_count=model.consecutive_failure_count,
            last_failure_category=(
                ProviderFailureCategory(model.last_failure_category)
                if model.last_failure_category is not None
                else None
            ),
            circuit_open_until=model.circuit_open_until,
            timeout_failure_count=model.timeout_failure_count,
            rate_limited_failure_count=model.rate_limited_failure_count,
            upstream_error_failure_count=model.upstream_error_failure_count,
            updated_at=model.updated_at,
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
