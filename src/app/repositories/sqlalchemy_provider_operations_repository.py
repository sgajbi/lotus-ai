from __future__ import annotations

from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.contracts.access_control import (
    AuthorizationCapabilityType,
    AuthorizationDecision,
    AuthorizationOutcome,
    TenantPolicyMode,
)
from app.contracts.providers import (
    ProviderFailureCategory,
    ProviderQuotaScope,
)
from app.contracts.provider_operations import ProviderOperationsControlActionType
from app.contracts.governed_actions import GovernedActionRecord
from app.db.models import (
    GovernedActionModel,
    ProviderBudgetStateModel,
    ProviderDegradationStateModel,
    ProviderOperationsEventModel,
    ProviderQuotaStateModel,
)
from app.repositories.provider_operations_repository import (
    ProviderBudgetStateRecord,
    ProviderDegradationStateRecord,
    ProviderOperationsEventRecord,
    ProviderOperationsRepository,
    ProviderQuotaStateRecord,
)
from app.repositories.sqlalchemy_repository_base import SqlAlchemyRepositoryBase


class SqlAlchemyProviderOperationsRepository(
    SqlAlchemyRepositoryBase, ProviderOperationsRepository
):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._ensure_sqlite_parent_directory()
        self._configure_sqlalchemy(database_url)

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
        for _ in range(2):
            with self._session_factory() as session:
                try:
                    model = session.execute(
                        select(ProviderQuotaStateModel)
                        .where(
                            ProviderQuotaStateModel.scope == scope.value,
                            ProviderQuotaStateModel.scope_key == scope_key,
                        )
                        .with_for_update()
                    ).scalar_one_or_none()
                    if model is None:
                        model = ProviderQuotaStateModel(
                            scope=scope.value,
                            scope_key=scope_key,
                            request_count=amount,
                            updated_at=updated_at,
                        )
                        session.add(model)
                    else:
                        model.request_count += amount
                        model.updated_at = updated_at
                    session.commit()
                    return self._to_quota_record(model)
                except IntegrityError:
                    session.rollback()
                    continue
        raise RuntimeError("Failed to increment provider quota state atomically.")

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
        for _ in range(2):
            with self._session_factory() as session:
                try:
                    model = session.execute(
                        select(ProviderBudgetStateModel)
                        .where(ProviderBudgetStateModel.budget_key == budget_key)
                        .with_for_update()
                    ).scalar_one_or_none()
                    if model is None:
                        model = ProviderBudgetStateModel(
                            budget_key=budget_key,
                            current_spend_usd=round(amount_usd, 8),
                            updated_at=updated_at,
                        )
                        session.add(model)
                    else:
                        model.current_spend_usd = round(model.current_spend_usd + amount_usd, 8)
                        model.updated_at = updated_at
                    session.commit()
                    return self._to_budget_record(model)
                except IntegrityError:
                    session.rollback()
                    continue
        raise RuntimeError("Failed to add provider budget spend atomically.")

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
        for _ in range(2):
            with self._session_factory() as session:
                try:
                    model = session.execute(
                        select(ProviderDegradationStateModel)
                        .where(ProviderDegradationStateModel.degradation_key == degradation_key)
                        .with_for_update()
                    ).scalar_one_or_none()
                    if model is None:
                        model = ProviderDegradationStateModel(
                            degradation_key=degradation_key,
                            consecutive_failure_count=1,
                            last_failure_category=category.value,
                            circuit_open_until=None,
                            timeout_failure_count=int(
                                category == ProviderFailureCategory.PROVIDER_TIMEOUT
                            ),
                            rate_limited_failure_count=int(
                                category == ProviderFailureCategory.PROVIDER_RATE_LIMITED
                            ),
                            upstream_error_failure_count=int(
                                category == ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR
                            ),
                            updated_at=updated_at,
                        )
                        session.add(model)
                    else:
                        model.consecutive_failure_count += 1
                        model.last_failure_category = category.value
                        model.timeout_failure_count += int(
                            category == ProviderFailureCategory.PROVIDER_TIMEOUT
                        )
                        model.rate_limited_failure_count += int(
                            category == ProviderFailureCategory.PROVIDER_RATE_LIMITED
                        )
                        model.upstream_error_failure_count += int(
                            category == ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR
                        )
                        model.updated_at = updated_at
                    session.commit()
                    return self._to_degradation_record(model)
                except IntegrityError:
                    session.rollback()
                    continue
        raise RuntimeError("Failed to record provider degradation failure atomically.")

    def reset_quota_states(
        self,
        *,
        scope: ProviderQuotaScope | None = None,
        scope_key: str | None = None,
    ) -> int:
        with self._session_factory() as session:
            statement = delete(ProviderQuotaStateModel)
            if scope is not None:
                statement = statement.where(ProviderQuotaStateModel.scope == scope.value)
            if scope_key is not None:
                statement = statement.where(ProviderQuotaStateModel.scope_key == scope_key)
            result = session.execute(statement)
            session.commit()
            return int(getattr(result, "rowcount", 0) or 0)

    def reset_budget_state(self, *, budget_key: str) -> int:
        with self._session_factory() as session:
            result = session.execute(
                delete(ProviderBudgetStateModel).where(
                    ProviderBudgetStateModel.budget_key == budget_key
                )
            )
            session.commit()
            return int(getattr(result, "rowcount", 0) or 0)

    def reset_degradation_state(self, *, degradation_key: str) -> int:
        with self._session_factory() as session:
            result = session.execute(
                delete(ProviderDegradationStateModel).where(
                    ProviderDegradationStateModel.degradation_key == degradation_key
                )
            )
            session.commit()
            return int(getattr(result, "rowcount", 0) or 0)

    def reset_degradation_states(self) -> int:
        with self._session_factory() as session:
            result = session.execute(delete(ProviderDegradationStateModel))
            session.commit()
            return int(getattr(result, "rowcount", 0) or 0)

    def save_operations_event(self, record: ProviderOperationsEventRecord) -> None:
        model = ProviderOperationsEventModel(
            event_id=record.event_id,
            action_type=record.action_type.value,
            scope=record.scope.value if record.scope is not None else None,
            scope_key=record.scope_key,
            reason=record.reason,
            requested_by=record.requested_by,
            approved_by=record.approved_by,
            affected_record_count=record.affected_record_count,
            authorization_payload=record.authorization.model_dump(mode="json"),
            recorded_at=record.recorded_at,
        )
        with self._session_factory() as session:
            session.add(model)
            session.commit()

    def list_operations_events(self, *, limit: int) -> list[ProviderOperationsEventRecord]:
        with self._session_factory() as session:
            models = session.scalars(
                select(ProviderOperationsEventModel)
                .order_by(ProviderOperationsEventModel.recorded_at.desc())
                .limit(limit)
            ).all()
            return [self._to_event_record(model) for model in models]

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

    def _to_event_record(
        self, model: ProviderOperationsEventModel
    ) -> ProviderOperationsEventRecord:
        return ProviderOperationsEventRecord(
            event_id=model.event_id,
            action_type=ProviderOperationsControlActionType(model.action_type),
            scope=ProviderQuotaScope(model.scope) if model.scope is not None else None,
            scope_key=model.scope_key,
            reason=model.reason,
            requested_by=model.requested_by,
            approved_by=model.approved_by,
            affected_record_count=model.affected_record_count,
            authorization=(
                AuthorizationDecision.model_validate(model.authorization_payload)
                if model.authorization_payload is not None
                else _build_legacy_control_authorization()
            ),
            recorded_at=model.recorded_at,
        )

    def get_governed_action(self, action_id: str) -> GovernedActionRecord | None:
        with self._session_factory() as session:
            model = session.get(GovernedActionModel, action_id)
            return _to_governed_action_record(model) if model is not None else None

    def get_pending_governed_action(
        self,
        *,
        action_type: str,
        target: str,
    ) -> GovernedActionRecord | None:
        with self._session_factory() as session:
            model = session.execute(
                select(GovernedActionModel)
                .where(
                    GovernedActionModel.action_type == action_type,
                    GovernedActionModel.target == target,
                    GovernedActionModel.status == "PENDING",
                )
                .limit(1)
            ).scalar_one_or_none()
            return _to_governed_action_record(model) if model is not None else None

    def list_governed_actions(
        self,
        *,
        status: str | None,
        target: str | None,
        limit: int,
    ) -> list[GovernedActionRecord]:
        with self._session_factory() as session:
            query = select(GovernedActionModel)
            if status is not None:
                query = query.where(GovernedActionModel.status == status)
            if target is not None:
                query = query.where(GovernedActionModel.target == target)
            query = query.order_by(GovernedActionModel.requested_at.desc()).limit(limit)
            return [_to_governed_action_record(model) for model in session.execute(query).scalars()]

    def upsert_governed_action(self, record: GovernedActionRecord) -> None:
        with self._session_factory() as session:
            model = session.get(GovernedActionModel, record.action_id)
            payload = record.model_dump(mode="json")
            if model is None:
                session.add(GovernedActionModel(**payload))
            else:
                for field, value in payload.items():
                    setattr(model, field, value)
            session.commit()

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
        capability_type=AuthorizationCapabilityType.PROVIDER_CONTROL,
        outcome=AuthorizationOutcome.ALLOWED,
        allowed=True,
        tenant_policy_mode=TenantPolicyMode.OPTIONAL,
        task_id=None,
        requested_source_ids=[],
        effective_source_ids=[],
        tenant_id=None,
        summary=(
            "Legacy provider control event predates explicit caller-authorization capture and is "
            "treated as a durable pre-RFC-0012 operator action."
        ),
    )


def _to_governed_action_record(model: GovernedActionModel) -> GovernedActionRecord:
    return GovernedActionRecord.model_validate(
        {column: getattr(model, column) for column in GovernedActionRecord.model_fields}
    )
