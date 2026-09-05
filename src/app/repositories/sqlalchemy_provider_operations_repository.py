from __future__ import annotations

from collections.abc import Sequence

from pathlib import Path

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError, OperationalError

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
    ProviderAttemptDebitModel,
    ProviderBudgetStateModel,
    ProviderDegradationStateModel,
    ProviderOperationsEventModel,
    ProviderQuotaStateModel,
)
from app.repositories.provider_operations_repository import (
    ProviderAttemptDebitRecord,
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

    def record_attempt_debit(self, record: ProviderAttemptDebitRecord, *, budget_key: str) -> bool:
        """Debit row and budget counter advance in ONE transaction: a crash
        between them cannot happen, and a duplicate identity is a complete
        no-op (the counter is untouched)."""

        with self._session_factory() as session:
            existing = session.get(ProviderAttemptDebitModel, record.debit_id)
            if existing is not None:
                return False
            session.add(
                ProviderAttemptDebitModel(
                    debit_id=record.debit_id,
                    provider_id=record.provider_id,
                    basis=record.basis,
                    amount_usd=record.amount_usd,
                    input_tokens=record.input_tokens,
                    output_tokens=record.output_tokens,
                    rate_card_ref=record.rate_card_ref,
                    recorded_at=record.recorded_at,
                    candidate_entry_id=record.candidate_entry_id,
                    model_revision=record.model_revision,
                    attempt_index=record.attempt_index,
                    candidate_id_v2=record.candidate_id_v2,
                )
            )
            budget = session.execute(
                select(ProviderBudgetStateModel)
                .where(ProviderBudgetStateModel.budget_key == budget_key)
                .with_for_update()
            ).scalar_one_or_none()
            if budget is None:
                session.add(
                    ProviderBudgetStateModel(
                        budget_key=budget_key,
                        current_spend_usd=round(record.amount_usd, 8),
                        updated_at=record.recorded_at,
                    )
                )
            else:
                budget.current_spend_usd = round(budget.current_spend_usd + record.amount_usd, 8)
                budget.updated_at = record.recorded_at
            try:
                session.commit()
            except IntegrityError:
                # A concurrent recorder won the same identity: their debit
                # stands, ours is the duplicate.
                session.rollback()
                return False
            return True

    def reserve_attempt_debit(
        self,
        record: ProviderAttemptDebitRecord,
        *,
        budget_key: str,
        hard_limit_usd: float | None,
    ) -> str:
        """Check-and-reserve in ONE transaction (issue #300). The limit
        check and the counter advance are a single guarded UPDATE - an
        atomic compare-and-swap on the budget row that holds on every SQL
        backend (row locks are a no-op on SQLite; a guarded statement is
        not) - so two replicas cannot both admit the last available budget.
        The debit row commits in the same transaction."""

        for _ in range(4):
            with self._session_factory() as session:
                try:
                    existing = session.get(ProviderAttemptDebitModel, record.debit_id)
                    if existing is not None:
                        return "DUPLICATE"
                    guarded = update(ProviderBudgetStateModel).where(
                        ProviderBudgetStateModel.budget_key == budget_key
                    )
                    if hard_limit_usd is not None:
                        guarded = guarded.where(
                            func.round(
                                ProviderBudgetStateModel.current_spend_usd + record.amount_usd,
                                8,
                            )
                            <= hard_limit_usd
                        )
                    result = session.execute(
                        guarded.values(
                            current_spend_usd=func.round(
                                ProviderBudgetStateModel.current_spend_usd + record.amount_usd,
                                8,
                            ),
                            updated_at=record.recorded_at,
                        )
                    )
                    if int(getattr(result, "rowcount", 0) or 0) == 0:
                        state = session.get(ProviderBudgetStateModel, budget_key)
                        if state is not None:
                            # The row exists, so the guard refused: reserving
                            # would push the counter past the hard limit.
                            session.rollback()
                            return "REFUSED"
                        if (
                            hard_limit_usd is not None
                            and round(record.amount_usd, 8) > hard_limit_usd
                        ):
                            session.rollback()
                            return "REFUSED"
                        session.add(
                            ProviderBudgetStateModel(
                                budget_key=budget_key,
                                current_spend_usd=round(record.amount_usd, 8),
                                updated_at=record.recorded_at,
                            )
                        )
                    session.add(
                        ProviderAttemptDebitModel(
                            debit_id=record.debit_id,
                            provider_id=record.provider_id,
                            basis=record.basis,
                            amount_usd=record.amount_usd,
                            input_tokens=record.input_tokens,
                            output_tokens=record.output_tokens,
                            rate_card_ref=record.rate_card_ref,
                            recorded_at=record.recorded_at,
                            candidate_entry_id=record.candidate_entry_id,
                            model_revision=record.model_revision,
                            attempt_index=record.attempt_index,
                            candidate_id_v2=record.candidate_id_v2,
                        )
                    )
                    session.commit()
                    return "RESERVED"
                except IntegrityError:
                    session.rollback()
                    if session.get(ProviderAttemptDebitModel, record.debit_id) is not None:
                        # A concurrent recorder won the same attempt identity.
                        return "DUPLICATE"
                    # Two replicas raced the first budget-row insert; retry -
                    # the guarded UPDATE now finds the row.
                    continue
                except OperationalError:
                    # Transient lock contention (SQLite lock upgrade,
                    # serialization conflicts): the transaction applied
                    # nothing - retry the whole guarded sequence.
                    session.rollback()
                    continue
        raise RuntimeError("Failed to reserve provider attempt debit atomically.")

    def settle_attempt_debit(
        self,
        *,
        debit_id: str,
        budget_key: str,
        basis: str,
        amount_usd: float,
        input_tokens: int | None,
        output_tokens: int | None,
        rate_card_ref: str | None,
        settled_at: str,
    ) -> bool:
        for _ in range(4):
            try:
                return self._settle_attempt_debit_once(
                    debit_id=debit_id,
                    budget_key=budget_key,
                    basis=basis,
                    amount_usd=amount_usd,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    rate_card_ref=rate_card_ref,
                    settled_at=settled_at,
                )
            except OperationalError:
                continue
        raise RuntimeError("Failed to settle provider attempt debit atomically.")

    def _settle_attempt_debit_once(
        self,
        *,
        debit_id: str,
        budget_key: str,
        basis: str,
        amount_usd: float,
        input_tokens: int | None,
        output_tokens: int | None,
        rate_card_ref: str | None,
        settled_at: str,
    ) -> bool:
        with self._session_factory() as session:
            row = session.get(ProviderAttemptDebitModel, debit_id)
            if row is None or row.basis != "RESERVED_MAX":
                return False
            reserved_amount = row.amount_usd
            delta = round(amount_usd - reserved_amount, 8)
            values: dict[str, object] = {
                "basis": basis,
                "amount_usd": amount_usd,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "recorded_at": settled_at,
            }
            if rate_card_ref is not None:
                values["rate_card_ref"] = rate_card_ref
            # Guarded on the reserved basis AND amount: only one settlement
            # can win the row (atomic on every backend), so the counter
            # adjustment below applies exactly once.
            result = session.execute(
                update(ProviderAttemptDebitModel)
                .where(
                    ProviderAttemptDebitModel.debit_id == debit_id,
                    ProviderAttemptDebitModel.basis == "RESERVED_MAX",
                    ProviderAttemptDebitModel.amount_usd == reserved_amount,
                )
                .values(**values)
            )
            if int(getattr(result, "rowcount", 0) or 0) == 0:
                session.rollback()
                return False
            session.execute(
                update(ProviderBudgetStateModel)
                .where(ProviderBudgetStateModel.budget_key == budget_key)
                .values(
                    current_spend_usd=func.round(
                        ProviderBudgetStateModel.current_spend_usd + delta, 8
                    ),
                    updated_at=settled_at,
                )
            )
            session.commit()
            return True

    def list_attempt_debits(self, *, limit: int = 100) -> Sequence[ProviderAttemptDebitRecord]:
        with self._session_factory() as session:
            models = session.scalars(
                select(ProviderAttemptDebitModel)
                .order_by(
                    ProviderAttemptDebitModel.recorded_at.desc(),
                    ProviderAttemptDebitModel.debit_id.desc(),
                )
                .limit(max(limit, 0))
            ).all()
            return [
                ProviderAttemptDebitRecord(
                    debit_id=model.debit_id,
                    provider_id=model.provider_id,
                    basis=model.basis,
                    amount_usd=model.amount_usd,
                    input_tokens=model.input_tokens,
                    output_tokens=model.output_tokens,
                    rate_card_ref=model.rate_card_ref,
                    recorded_at=model.recorded_at,
                    candidate_entry_id=model.candidate_entry_id,
                    model_revision=model.model_revision,
                    attempt_index=model.attempt_index,
                    candidate_id_v2=model.candidate_id_v2,
                )
                for model in models
            ]

    def delete_attempt_debits(self, debit_ids: Sequence[str]) -> int:
        if not debit_ids:
            return 0
        with self._session_factory() as session:
            result = session.execute(
                delete(ProviderAttemptDebitModel).where(
                    ProviderAttemptDebitModel.debit_id.in_(list(debit_ids))
                )
            )
            session.commit()
            return int(getattr(result, "rowcount", 0) or 0)

    def sum_attempt_debits(self, *, debit_id_prefix: str) -> float:
        with self._session_factory() as session:
            total = session.execute(
                select(func.coalesce(func.sum(ProviderAttemptDebitModel.amount_usd), 0.0)).where(
                    # Identities are adbt:<uuid-hex>:<candidate-entry-id>:<index>;
                    # none of those parts contain SQL LIKE wildcards.
                    ProviderAttemptDebitModel.debit_id.like(f"{debit_id_prefix}%")
                )
            ).scalar_one()
            return round(float(total), 8)

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

    def delete_operations_events(self, event_ids: Sequence[str]) -> int:
        if not event_ids:
            return 0
        with self._session_factory() as session:
            result = session.execute(
                delete(ProviderOperationsEventModel).where(
                    ProviderOperationsEventModel.event_id.in_(list(event_ids))
                )
            )
            session.commit()
            return int(getattr(result, "rowcount", 0) or 0)

    def delete_governed_actions(self, action_ids: Sequence[str]) -> int:
        if not action_ids:
            return 0
        with self._session_factory() as session:
            result = session.execute(
                delete(GovernedActionModel).where(
                    GovernedActionModel.action_id.in_(list(action_ids))
                )
            )
            session.commit()
            return int(getattr(result, "rowcount", 0) or 0)

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

    def transition_governed_action(
        self,
        *,
        action_id: str,
        expected_status: str,
        record: GovernedActionRecord,
    ) -> bool:
        # One guarded UPDATE in its own transaction (issue #327): the WHERE
        # predicate on the CURRENT status is the cross-replica claim - two
        # sessions cannot both move the same action out of expected_status.
        payload = record.model_dump(mode="json")
        payload.pop("action_id", None)
        with self._session_factory() as session:
            result = session.execute(
                update(GovernedActionModel)
                .where(
                    GovernedActionModel.action_id == action_id,
                    GovernedActionModel.status == expected_status,
                )
                .values(**payload)
            )
            session.commit()
            return int(getattr(result, "rowcount", 0) or 0) == 1

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
