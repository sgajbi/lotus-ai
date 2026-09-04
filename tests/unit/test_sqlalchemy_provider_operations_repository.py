from pathlib import Path
from typing import Any, cast

from sqlalchemy.exc import IntegrityError

from app.contracts.access_control import (
    AuthorizationCapabilityType,
    AuthorizationDecision,
    AuthorizationOutcome,
    TenantPolicyMode,
)
from app.contracts.providers import ProviderFailureCategory, ProviderQuotaScope
from app.repositories.provider_operations_repository import (
    ProviderBudgetStateRecord,
    ProviderDegradationStateRecord,
    ProviderOperationsEventRecord,
    ProviderQuotaStateRecord,
)
from app.contracts.provider_operations import ProviderOperationsControlActionType
from app.repositories.sqlalchemy_provider_operations_repository import (
    SqlAlchemyProviderOperationsRepository,
)
from tests.support.migration_runner import upgrade_database_to_head


def _authorization() -> AuthorizationDecision:
    return AuthorizationDecision(
        caller_app="lotus-platform",
        capability_type=AuthorizationCapabilityType.PROVIDER_CONTROL,
        outcome=AuthorizationOutcome.ALLOWED,
        allowed=True,
        tenant_policy_mode=TenantPolicyMode.OPTIONAL,
        task_id=None,
        requested_source_ids=[],
        effective_source_ids=[],
        tenant_id=None,
        summary="Allowed provider control decision.",
    )


def test_sqlalchemy_provider_operations_repository_round_trip(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-provider-ops.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyProviderOperationsRepository(database_url)

    repository.save_quota_state(
        ProviderQuotaStateRecord(
            scope=ProviderQuotaScope.TENANT,
            scope_key="tenant-a",
            request_count=4,
            updated_at="2026-03-23T00:00:00Z",
        )
    )
    repository.save_budget_state(
        ProviderBudgetStateRecord(
            budget_key="live_text_generation",
            current_spend_usd=42.25,
            updated_at="2026-03-23T00:01:00Z",
        )
    )
    repository.save_degradation_state(
        ProviderDegradationStateRecord(
            degradation_key="live_text_generation",
            consecutive_failure_count=5,
            last_failure_category=ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR,
            circuit_open_until="2026-03-23T00:10:00Z",
            timeout_failure_count=1,
            rate_limited_failure_count=1,
            upstream_error_failure_count=3,
            updated_at="2026-03-23T00:02:00Z",
        )
    )

    quota = repository.get_quota_state(scope=ProviderQuotaScope.TENANT, scope_key="tenant-a")
    budget = repository.get_budget_state(budget_key="live_text_generation")
    degradation = repository.get_degradation_state(degradation_key="live_text_generation")

    assert quota is not None
    assert quota.request_count == 4
    assert repository.list_quota_states() == [quota]
    assert budget is not None
    assert budget.current_spend_usd == 42.25
    assert degradation is not None
    assert degradation.last_failure_category == ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR
    assert degradation.upstream_error_failure_count == 3


def test_sqlalchemy_provider_operations_repository_returns_none_for_unknown_records(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-provider-ops.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyProviderOperationsRepository(database_url)

    assert repository.list_quota_states() == []
    assert repository.get_quota_state(scope=ProviderQuotaScope.DEFAULT, scope_key="global") is None
    assert repository.get_budget_state(budget_key="missing") is None
    assert repository.get_degradation_state(degradation_key="missing") is None


def test_sqlalchemy_provider_operations_repository_creates_parent_directory_for_sqlite_file(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "nested" / "db" / "lotus-ai-provider-ops.db"
    database_url = f"sqlite:///{db_path}"

    SqlAlchemyProviderOperationsRepository(database_url)

    assert db_path.parent.is_dir()


def test_sqlalchemy_provider_operations_repository_applies_atomic_mutations(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-provider-ops.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyProviderOperationsRepository(database_url)

    quota = repository.increment_quota_state(
        scope=ProviderQuotaScope.DEFAULT,
        scope_key="global",
        amount=1,
        updated_at="2026-03-23T00:00:00Z",
    )
    budget = repository.add_budget_spend(
        budget_key="live_text_generation",
        amount_usd=0.75,
        updated_at="2026-03-23T00:01:00Z",
    )
    degradation = repository.record_degradation_failure(
        degradation_key="live_text_generation",
        category=ProviderFailureCategory.PROVIDER_TIMEOUT,
        updated_at="2026-03-23T00:02:00Z",
    )
    quota = repository.increment_quota_state(
        scope=ProviderQuotaScope.DEFAULT,
        scope_key="global",
        amount=1,
        updated_at="2026-03-23T00:03:00Z",
    )
    budget = repository.add_budget_spend(
        budget_key="live_text_generation",
        amount_usd=0.25,
        updated_at="2026-03-23T00:04:00Z",
    )
    degradation = repository.record_degradation_failure(
        degradation_key="live_text_generation",
        category=ProviderFailureCategory.PROVIDER_UPSTREAM_ERROR,
        updated_at="2026-03-23T00:05:00Z",
    )

    assert quota.request_count == 2
    assert budget.current_spend_usd == 1.0
    assert degradation.consecutive_failure_count == 2
    assert degradation.timeout_failure_count == 1
    assert degradation.upstream_error_failure_count == 1


def test_sqlalchemy_attempt_debits_are_idempotent_and_transactional(
    tmp_path: Path,
) -> None:
    """Issue #289: the debit row and the budget counter advance together in
    one transaction, a duplicate identity is a complete no-op, and deleting
    evidence never reverses the counter."""

    from app.repositories.provider_operations_repository import ProviderAttemptDebitRecord

    database_url = f"sqlite:///{tmp_path / 'lotus-ai-provider-debits.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyProviderOperationsRepository(database_url)

    debit = ProviderAttemptDebitRecord(
        debit_id="adbt:exec-sql:text.openai:0",
        provider_id="text.openai",
        basis="CONSERVATIVE_ESTIMATE",
        amount_usd=0.01736,
        input_tokens=200,
        output_tokens=512,
        rate_card_ref="default-live-text",
        recorded_at="2026-03-23T00:00:00Z",
    )

    assert repository.record_attempt_debit(debit, budget_key="live_text_generation") is True
    assert repository.record_attempt_debit(debit, budget_key="live_text_generation") is False

    budget = repository.get_budget_state(budget_key="live_text_generation")
    assert budget is not None
    assert budget.current_spend_usd == 0.01736

    rows = repository.list_attempt_debits(limit=10)
    assert [row.debit_id for row in rows] == ["adbt:exec-sql:text.openai:0"]
    assert rows[0].basis == "CONSERVATIVE_ESTIMATE"
    assert rows[0].input_tokens == 200

    assert repository.delete_attempt_debits([]) == 0
    assert repository.delete_attempt_debits(["adbt:exec-sql:text.openai:0", "missing"]) == 1
    assert repository.list_attempt_debits(limit=10) == []
    # Evidence expiry never refunds the envelope.
    budget = repository.get_budget_state(budget_key="live_text_generation")
    assert budget is not None
    assert budget.current_spend_usd == 0.01736


def test_sqlalchemy_provider_operations_repository_records_events_and_resets_state(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-provider-ops.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyProviderOperationsRepository(database_url)

    repository.increment_quota_state(
        scope=ProviderQuotaScope.DEFAULT,
        scope_key="global",
        amount=1,
        updated_at="2026-03-23T00:00:00Z",
    )
    repository.add_budget_spend(
        budget_key="live_text_generation",
        amount_usd=0.75,
        updated_at="2026-03-23T00:01:00Z",
    )
    repository.record_degradation_failure(
        degradation_key="live_text_generation",
        category=ProviderFailureCategory.PROVIDER_TIMEOUT,
        updated_at="2026-03-23T00:02:00Z",
    )
    repository.save_operations_event(
        ProviderOperationsEventRecord(
            event_id="evt-1",
            action_type=ProviderOperationsControlActionType.RESET_ALL_PROVIDER_OPERATIONS,
            scope=None,
            scope_key=None,
            reason="Operator reset after review",
            requested_by="ops.user@lotus",
            approved_by="approver.user@lotus",
            affected_record_count=3,
            authorization=_authorization(),
            recorded_at="2026-03-23T00:03:00Z",
        )
    )

    assert repository.reset_quota_states() == 1
    assert repository.reset_budget_state(budget_key="live_text_generation") == 1
    assert repository.reset_degradation_state(degradation_key="live_text_generation") == 1
    events = repository.list_operations_events(limit=10)

    assert len(events) == 1
    assert events[0].event_id == "evt-1"
    assert (
        events[0].action_type == ProviderOperationsControlActionType.RESET_ALL_PROVIDER_OPERATIONS
    )
    assert events[0].authorization.outcome == AuthorizationOutcome.ALLOWED
    assert repository.list_quota_states() == []
    assert repository.get_budget_state(budget_key="live_text_generation") is None
    assert repository.get_degradation_state(degradation_key="live_text_generation") is None


class _IntegrityErrorSession:
    def __enter__(self) -> "_IntegrityErrorSession":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, *args: object, **kwargs: object) -> object:
        raise IntegrityError("statement", {}, Exception("duplicate"))

    def rollback(self) -> None:
        return None


def _integrity_error_session_factory() -> _IntegrityErrorSession:
    return _IntegrityErrorSession()


def _repository_with_integrity_error_session() -> SqlAlchemyProviderOperationsRepository:
    repository = object.__new__(SqlAlchemyProviderOperationsRepository)
    cast(Any, repository)._session_factory = _integrity_error_session_factory
    return repository


def test_sqlalchemy_provider_operations_repository_fails_after_retry_exhaustion() -> None:
    repository = _repository_with_integrity_error_session()

    for operation in (
        lambda: repository.increment_quota_state(
            scope=ProviderQuotaScope.DEFAULT,
            scope_key="global",
            amount=1,
            updated_at="2026-04-21T00:00:00Z",
        ),
        lambda: repository.add_budget_spend(
            budget_key="live_text_generation",
            amount_usd=1.0,
            updated_at="2026-04-21T00:00:00Z",
        ),
        lambda: repository.record_degradation_failure(
            degradation_key="live_text_generation",
            category=ProviderFailureCategory.PROVIDER_TIMEOUT,
            updated_at="2026-04-21T00:00:00Z",
        ),
    ):
        try:
            operation()
        except RuntimeError as exc:
            assert "Failed to" in str(exc)
            assert "atomically" in str(exc)
        else:
            raise AssertionError("Expected SQL retry exhaustion to raise RuntimeError")


def test_sqlalchemy_provider_operations_repository_sqlite_parent_handling(
    tmp_path: Path,
) -> None:
    repository = object.__new__(SqlAlchemyProviderOperationsRepository)

    repository._database_url = "postgresql://example"
    repository._ensure_sqlite_parent_directory()

    repository._database_url = "sqlite:///:memory:"
    repository._ensure_sqlite_parent_directory()

    relative_db_path = tmp_path / "relative" / "provider-ops.db"
    repository._database_url = f"sqlite:///{relative_db_path}"
    repository._ensure_sqlite_parent_directory()

    assert relative_db_path.parent.is_dir()


def test_governed_action_round_trip_and_pending_lookup(tmp_path: Path) -> None:
    """Issue #157: the evidence chain is durable, and the pending lookup that
    supersession depends on behaves identically to the memory adapter."""

    from app.contracts.governed_actions import (
        GovernedActionRecord,
        GovernedActionStatus,
        GovernedActionType,
        GovernedActorClass,
    )

    database_url = f"sqlite:///{tmp_path / 'lotus-ai-governed-actions.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyProviderOperationsRepository(database_url)

    record = GovernedActionRecord(
        action_id="gact_sql_parity_001",
        action_type=GovernedActionType.KILL_SWITCH_CLEAR,
        actor_class=GovernedActorClass.HUMAN_APPROVED,
        status=GovernedActionStatus.PENDING,
        target="ksw_sql_parity",
        action_hash="a" * 64,
        action_payload={"switch_id": "ksw_sql_parity", "clear_reason": "resolved"},
        requester_caller_app="lotus-platform",
        requester_trust_source="verified_service_jwt",
        requester_key_id="ops-key-alpha",
        requester_attribution="ops.primary@lotus",
        requested_at="2026-09-02T08:00:00+00:00",
    )
    repository.upsert_governed_action(record)

    assert repository.get_governed_action("gact_sql_parity_001") == record
    assert (
        repository.get_pending_governed_action(
            action_type="KILL_SWITCH_CLEAR", target="ksw_sql_parity"
        )
        == record
    )
    assert (
        repository.get_pending_governed_action(action_type="KILL_SWITCH_CLEAR", target="ksw_other")
        is None
    )

    executed = record.model_copy(
        update={
            "status": GovernedActionStatus.EXECUTED,
            "approver_caller_app": "lotus-platform",
            "approver_trust_source": "verified_service_jwt",
            "approver_key_id": "ops-key-beta",
            "approved_at": "2026-09-02T08:05:00+00:00",
            "executed_at": "2026-09-02T08:05:00+00:00",
        }
    )
    repository.upsert_governed_action(executed)

    assert repository.get_governed_action("gact_sql_parity_001") == executed
    # An executed action is no longer pending.
    assert (
        repository.get_pending_governed_action(
            action_type="KILL_SWITCH_CLEAR", target="ksw_sql_parity"
        )
        is None
    )
