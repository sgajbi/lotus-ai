"""Governed-claim and budget CAS fences on real PostgreSQL (issue #344).

Every scenario runs two INDEPENDENT repository instances - separate engines,
separate connection pools, genuinely separate PostgreSQL backends (proven by
pg_backend_pid below) - racing the same single-statement guarded UPDATE
through a barrier. The scenarios mirror their SQLite counterparts 1:1
(tests/unit/test_governed_execution_ownership.py for claims,
tests/unit/test_budget_exposure.py for exposure) so drift between the two
backends stays visible. If any fence behaves differently here than on
SQLite, that is a P1 defect in the fence, never a test adjustment.

Isolation baseline: READ COMMITTED (PostgreSQL's default, asserted below).
Under it a blocked guarded UPDATE re-evaluates its WHERE against the
committed winner and simply matches zero rows - no serialization failures
arise for single-statement CAS, which is why the fences need no isolation
tuning. The REPEATABLE READ scenario at the bottom exercises the loser's
serialization failure and the repository's retry-and-converge path.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from typing import TypeVar
from uuid import uuid4

from sqlalchemy import event, select, text
from sqlalchemy.engine import ExceptionContext
from sqlalchemy.orm import Session, sessionmaker

from app.contracts.governed_actions import (
    GovernedActionRecord,
    GovernedActionStatus,
    GovernedActionType,
    GovernedActorClass,
)
from app.db.models import ProviderAttemptDebitModel
from app.repositories.provider_operations_repository import ProviderAttemptDebitRecord
from app.repositories.sqlalchemy_provider_operations_repository import (
    SqlAlchemyProviderOperationsRepository,
)

_T = TypeVar("_T")

_T0 = "2026-09-06T00:00:00Z"
_T1 = "2026-09-06T00:00:01Z"
_PAYLOAD: dict[str, str | None] = {
    "action_type": "PROVIDER_OPERATIONS_RESET",
    "target": "live",
}


def _race(*calls: Callable[[], _T]) -> list[_T]:
    """Run the calls through a shared barrier so their guarded statements
    genuinely overlap on the database, not merely on the thread pool."""

    barrier = Barrier(len(calls), timeout=10)

    def runner(call: Callable[[], _T]) -> _T:
        barrier.wait()
        return call()

    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        return list(pool.map(runner, calls))


def _two_sessions(
    database_url: str,
) -> tuple[SqlAlchemyProviderOperationsRepository, SqlAlchemyProviderOperationsRepository]:
    return (
        SqlAlchemyProviderOperationsRepository(database_url),
        SqlAlchemyProviderOperationsRepository(database_url),
    )


def _pending_action(action_id: str) -> GovernedActionRecord:
    return GovernedActionRecord(
        action_id=action_id,
        action_type=GovernedActionType.PROVIDER_OPERATIONS_RESET,
        actor_class=GovernedActorClass.HUMAN_APPROVED,
        status=GovernedActionStatus.PENDING,
        target="live",
        action_hash="a" * 64,
        action_payload=dict(_PAYLOAD),
        requester_caller_app="operator-service",
        requester_trust_source="verified_service_jwt",
        requester_key_id="key-a",
        requested_at=_T0,
    )


def _claimed_action(action_id: str, *, claimed_at: str = _T0) -> GovernedActionRecord:
    return _pending_action(action_id).model_copy(
        update={
            "status": GovernedActionStatus.CLAIMED,
            "approver_caller_app": "operator-service",
            "approver_trust_source": "verified_service_jwt",
            "approver_key_id": "key-b",
            "claimed_at": claimed_at,
        }
    )


def _reserved_debit(debit_id: str, *, amount_usd: float) -> ProviderAttemptDebitRecord:
    return ProviderAttemptDebitRecord(
        debit_id=debit_id,
        provider_id="text.openai",
        basis="RESERVED_MAX",
        amount_usd=amount_usd,
        input_tokens=200,
        output_tokens=512,
        rate_card_ref="default-live-text",
        recorded_at=_T0,
        candidate_entry_id="text.openai:gpt-5.4",
        model_revision="gpt-5.4",
        attempt_index=0,
        candidate_id_v2=f"cand2_{'f' * 64}",
    )


def test_fence_sessions_are_independent_read_committed_connections(
    postgres_database_url: str,
) -> None:
    """The issue's aliasing edge case: two repository instances must reach
    PostgreSQL as two backends, and the fences run on the READ COMMITTED
    baseline this module documents."""

    session_a, session_b = _two_sessions(postgres_database_url)
    pids = []
    isolation_levels = []
    for repository in (session_a, session_b):
        with repository._session_factory() as session:
            pids.append(session.execute(text("SELECT pg_backend_pid()")).scalar_one())
            isolation_levels.append(
                session.execute(text("SHOW transaction_isolation")).scalar_one()
            )
    assert pids[0] != pids[1], "the two 'independent' sessions alias one backend"
    assert isolation_levels == ["read committed", "read committed"]


def test_claim_fence_admits_exactly_one_session(postgres_database_url: str) -> None:
    """Scenario 1 - mirror of the SQLite two-session claim race: two
    approvers race PENDING->CLAIMED on one action; the guarded status
    predicate admits exactly one."""

    session_a, session_b = _two_sessions(postgres_database_url)
    action_id = f"gact_pg_claim_{uuid4().hex}"
    session_a.upsert_governed_action(_pending_action(action_id))

    def claim(session: SqlAlchemyProviderOperationsRepository, key: str) -> bool:
        return session.transition_governed_action(
            action_id=action_id,
            expected_status=GovernedActionStatus.PENDING.value,
            record=_claimed_action(action_id).model_copy(update={"approver_key_id": key}),
        )

    outcomes = _race(lambda: claim(session_a, "key-b"), lambda: claim(session_b, "key-c"))
    assert sorted(outcomes) == [False, True]
    stored = session_a.get_governed_action(action_id)
    assert stored is not None
    assert stored.status is GovernedActionStatus.CLAIMED
    winner_key = "key-b" if outcomes[0] else "key-c"
    assert stored.approver_key_id == winner_key


def test_rotation_fence_admits_one_resumer_and_stale_finalization_loses(
    postgres_database_url: str,
) -> None:
    """Scenario 2 - two resumers of the same interrupted claim race the
    CLAIMED->CLAIMED rotation on the stale instant; one wins, and a
    finalization still fenced to the stale instant loses to the rotation."""

    session_a, session_b = _two_sessions(postgres_database_url)
    action_id = f"gact_pg_rotate_{uuid4().hex}"
    session_a.upsert_governed_action(_claimed_action(action_id, claimed_at=_T0))
    rotated_a = _claimed_action(action_id, claimed_at="2026-09-06T00:00:01.000001Z")
    rotated_b = _claimed_action(action_id, claimed_at="2026-09-06T00:00:01.000002Z")

    def rotate(
        session: SqlAlchemyProviderOperationsRepository, record: GovernedActionRecord
    ) -> bool:
        return session.transition_governed_action(
            action_id=action_id,
            expected_status=GovernedActionStatus.CLAIMED.value,
            record=record,
            expected_claimed_at=_T0,
        )

    outcomes = _race(lambda: rotate(session_a, rotated_a), lambda: rotate(session_b, rotated_b))
    assert sorted(outcomes) == [False, True]
    winner = rotated_a if outcomes[0] else rotated_b
    assert winner.claimed_at is not None

    executed = winner.model_copy(
        update={"status": GovernedActionStatus.EXECUTED, "executed_at": _T1}
    )
    stale_finalization = session_b.transition_governed_action(
        action_id=action_id,
        expected_status=GovernedActionStatus.CLAIMED.value,
        record=executed,
        expected_claimed_at=_T0,
    )
    assert stale_finalization is False
    owned_finalization = session_a.transition_governed_action(
        action_id=action_id,
        expected_status=GovernedActionStatus.CLAIMED.value,
        record=executed,
        expected_claimed_at=winner.claimed_at,
    )
    assert owned_finalization is True
    stored = session_b.get_governed_action(action_id)
    assert stored is not None
    assert stored.status is GovernedActionStatus.EXECUTED


def test_release_and_resume_race_on_one_claim_admits_one_winner(
    postgres_database_url: str,
) -> None:
    """Scenario 5 - #340's guarantee on PG: a governed claim release
    (CLAIMED->PENDING) and the frozen credential's own resume rotation race
    the SAME claim-instant fence; exactly one wins and the loser's follow-up
    on the stale instant refuses."""

    session_a, session_b = _two_sessions(postgres_database_url)
    action_id = f"gact_pg_release_{uuid4().hex}"
    session_a.upsert_governed_action(_claimed_action(action_id, claimed_at=_T0))
    released = _pending_action(action_id)
    resumed = _claimed_action(action_id, claimed_at=_T1)

    def release() -> bool:
        return session_a.transition_governed_action(
            action_id=action_id,
            expected_status=GovernedActionStatus.CLAIMED.value,
            record=released,
            expected_claimed_at=_T0,
        )

    def resume() -> bool:
        return session_b.transition_governed_action(
            action_id=action_id,
            expected_status=GovernedActionStatus.CLAIMED.value,
            record=resumed,
            expected_claimed_at=_T0,
        )

    release_won, resume_won = _race(release, resume)
    assert sorted([release_won, resume_won]) == [False, True]
    stored = session_a.get_governed_action(action_id)
    assert stored is not None
    if release_won:
        assert stored.status is GovernedActionStatus.PENDING
        assert stored.approver_key_id is None and stored.claimed_at is None
    else:
        assert stored.status is GovernedActionStatus.CLAIMED
        assert stored.claimed_at == _T1
    # The loser retrying on the stale instant stays refused either way.
    loser_retry = release if resume_won else resume
    assert loser_retry() is False


def test_reserve_admission_last_headroom_admits_exactly_one(
    postgres_database_url: str,
) -> None:
    """Scenario 4 - the #300 guarantee on PG: two sessions race the last
    available hard-budget headroom (and the first-write creation of the
    budget row itself); one RESERVED, one REFUSED, counter advanced once."""

    session_a, session_b = _two_sessions(postgres_database_url)
    budget_key = f"pg_admission_{uuid4().hex}"
    debit_a = _reserved_debit(f"adbt2:pg-admission-{uuid4().hex}:cand2_a:0", amount_usd=1.0)
    debit_b = _reserved_debit(f"adbt2:pg-admission-{uuid4().hex}:cand2_b:0", amount_usd=1.0)

    outcomes = _race(
        lambda: session_a.reserve_attempt_debit(debit_a, budget_key=budget_key, hard_limit_usd=1.5),
        lambda: session_b.reserve_attempt_debit(debit_b, budget_key=budget_key, hard_limit_usd=1.5),
    )
    assert sorted(outcomes) == ["REFUSED", "RESERVED"]
    budget = session_a.get_budget_state(budget_key=budget_key)
    assert budget is not None
    assert budget.current_spend_usd == 1.0
    admitted = debit_a if outcomes[0] == "RESERVED" else debit_b
    refused = debit_b if admitted is debit_a else debit_a
    assert session_a.get_attempt_debit(debit_id=admitted.debit_id) is not None
    assert session_a.get_attempt_debit(debit_id=refused.debit_id) is None


def test_reconcile_releases_exactly_once_across_sessions(
    postgres_database_url: str,
) -> None:
    """Scenario 3 - mirror of the SQLite reconciliation race: one
    UNRESOLVED_MAX exposure, two sessions racing the guarded basis+amount
    CAS; the counter adjusts exactly once and a late arrival refuses."""

    session_a, session_b = _two_sessions(postgres_database_url)
    budget_key = f"pg_reconcile_{uuid4().hex}"
    record = _reserved_debit(f"adbt2:pg-reconcile-{uuid4().hex}:cand2_x:0", amount_usd=1.10)
    assert (
        session_a.reserve_attempt_debit(record, budget_key=budget_key, hard_limit_usd=None)
        == "RESERVED"
    )
    assert session_a.hold_attempt_debit_unresolved(debit_id=record.debit_id, held_at=_T1)
    # Idempotent: a crash-retry of the hold is a no-op.
    assert session_a.hold_attempt_debit_unresolved(debit_id=record.debit_id, held_at=_T1) is False

    def reconcile(session: SqlAlchemyProviderOperationsRepository, tag: str) -> bool:
        return session.reconcile_attempt_debit(
            debit_id=record.debit_id,
            budget_key=budget_key,
            amount_usd=0.42,
            input_tokens=100,
            output_tokens=40,
            rate_card_ref="default-live-text",
            reconciled_at=f"2026-09-06T00:00:03Z+{tag}",
        )

    outcomes = _race(lambda: reconcile(session_a, "a"), lambda: reconcile(session_b, "b"))
    assert sorted(outcomes) == [False, True]
    assert reconcile(session_a, "late") is False
    budget = session_a.get_budget_state(budget_key=budget_key)
    assert budget is not None
    assert budget.current_spend_usd == 0.42
    row = session_b.get_attempt_debit(debit_id=record.debit_id)
    assert row is not None
    assert row.basis == "RECONCILED"


def test_settle_and_hold_race_resolves_the_row_exactly_once(
    postgres_database_url: str,
) -> None:
    """Settle-vs-hold on one reservation: whichever transition wins the
    RESERVED_MAX guard, the row ends in exactly one terminal basis and the
    counter matches that winner - never a double resolution."""

    session_a, session_b = _two_sessions(postgres_database_url)
    budget_key = f"pg_settle_hold_{uuid4().hex}"
    record = _reserved_debit(f"adbt2:pg-settle-hold-{uuid4().hex}:cand2_y:0", amount_usd=1.0)
    assert (
        session_a.reserve_attempt_debit(record, budget_key=budget_key, hard_limit_usd=None)
        == "RESERVED"
    )

    def settle() -> bool:
        return session_a.settle_attempt_debit(
            debit_id=record.debit_id,
            budget_key=budget_key,
            basis="ACTUAL_USAGE",
            amount_usd=0.4,
            input_tokens=90,
            output_tokens=30,
            rate_card_ref="default-live-text",
            settled_at=_T1,
        )

    def hold() -> bool:
        return session_b.hold_attempt_debit_unresolved(debit_id=record.debit_id, held_at=_T1)

    settle_won, hold_won = _race(settle, hold)
    assert sorted([settle_won, hold_won]) == [False, True]
    budget = session_a.get_budget_state(budget_key=budget_key)
    row = session_b.get_attempt_debit(debit_id=record.debit_id)
    assert budget is not None and row is not None
    if settle_won:
        assert row.basis == "ACTUAL_USAGE"
        assert row.amount_usd == 0.4
        assert budget.current_spend_usd == 0.4
    else:
        assert row.basis == "UNRESOLVED_MAX"
        assert row.amount_usd == 1.0
        assert budget.current_spend_usd == 1.0


def test_release_and_hold_race_resolves_the_row_exactly_once(
    postgres_database_url: str,
) -> None:
    """The non-billable release racing the hold. Both resolve a RESERVED_MAX
    row but in OPPOSITE budget directions - a proven non-billable attempt
    (429 refused before generation) releases the whole reservation to zero,
    while unpriceable billable exposure holds the reserved maximum. Exactly
    one wins, and the counter follows that winner: the settle-vs-hold test
    below covers the same fence for evidenced ACTUAL_USAGE."""

    session_a, session_b = _two_sessions(postgres_database_url)
    budget_key = f"pg_release_hold_{uuid4().hex}"
    record = _reserved_debit(f"adbt2:pg-release-hold-{uuid4().hex}:cand2_r:0", amount_usd=1.0)
    assert (
        session_a.reserve_attempt_debit(record, budget_key=budget_key, hard_limit_usd=None)
        == "RESERVED"
    )

    def release() -> bool:
        # What settle_attempt_spend issues for billable_risk=False.
        return session_a.settle_attempt_debit(
            debit_id=record.debit_id,
            budget_key=budget_key,
            basis="RELEASED",
            amount_usd=0.0,
            input_tokens=None,
            output_tokens=None,
            rate_card_ref=None,
            settled_at=_T1,
        )

    def hold() -> bool:
        return session_b.hold_attempt_debit_unresolved(debit_id=record.debit_id, held_at=_T1)

    release_won, hold_won = _race(release, hold)
    assert sorted([release_won, hold_won]) == [False, True]
    budget = session_a.get_budget_state(budget_key=budget_key)
    row = session_b.get_attempt_debit(debit_id=record.debit_id)
    assert budget is not None and row is not None
    if release_won:
        assert row.basis == "RELEASED"
        assert row.amount_usd == 0.0
        # The full reservation came back: nothing was billable.
        assert budget.current_spend_usd == 0.0
    else:
        assert row.basis == "UNRESOLVED_MAX"
        assert row.amount_usd == 1.0
        assert budget.current_spend_usd == 1.0


class _RepeatableReadProviderOperationsRepository(SqlAlchemyProviderOperationsRepository):
    """The fences never require elevated isolation; this subclass exists to
    prove the loser's serialization failure under REPEATABLE READ funnels
    into the repository's existing OperationalError retry-and-converge path
    (the issue's 'retry-on-serialization exercised at least once')."""

    def _configure_sqlalchemy(self, database_url: str) -> None:
        super()._configure_sqlalchemy(database_url)
        self._engine = self._engine.execution_options(isolation_level="REPEATABLE READ")
        self._session_factory = sessionmaker(bind=self._engine, autoflush=False, future=True)


def test_repeatable_read_conflict_raises_40001_and_the_repository_converges(
    postgres_database_url: str,
) -> None:
    """Retry certification, not retry assumption.

    A barrier around two repository calls proves only that both ENTERED at
    the same time; under REPEATABLE READ the snapshot opens at the
    transaction's first statement, so two barrier-synchronised calls can
    still execute sequentially and produce the same [False, True] as a real
    conflict. That outcome is therefore not evidence of a retry.

    This test forces the ordering instead: the loser's transaction opens its
    snapshot with a priming read, the winner then commits its own
    transition, and only then does the loser's guarded UPDATE run - which
    PostgreSQL must refuse with SQLSTATE 40001 (serialization_failure). The
    40001 is OBSERVED at the engine's error boundary rather than inferred,
    and the assertion is that the repository's retry loop then opens a fresh
    snapshot and converges to an honest False. Remove the retry handling and
    the OperationalError escapes instead: the call raises, and this test
    fails.
    """

    winner = SqlAlchemyProviderOperationsRepository(postgres_database_url)
    loser = _RepeatableReadProviderOperationsRepository(postgres_database_url)
    budget_key = f"pg_rr_{uuid4().hex}"
    record = _reserved_debit(f"adbt2:pg-rr-{uuid4().hex}:cand2_z:0", amount_usd=1.0)
    assert (
        winner.reserve_attempt_debit(record, budget_key=budget_key, hard_limit_usd=None)
        == "RESERVED"
    )

    observed_sqlstates: list[str] = []

    @event.listens_for(loser._engine, "handle_error")
    def _capture_sqlstate(context: ExceptionContext) -> None:
        sqlstate = getattr(context.original_exception, "sqlstate", None)
        if sqlstate is not None:
            observed_sqlstates.append(str(sqlstate))

    snapshot_open = Event()
    winner_committed = Event()
    sessions_opened = {"count": 0}
    real_factory = loser._session_factory

    def priming_session_factory() -> Session:
        session = real_factory()
        sessions_opened["count"] += 1
        if sessions_opened["count"] == 1:
            # First statement in this transaction: under REPEATABLE READ it
            # pins the snapshot, BEFORE the winner commits. The retry's
            # second session is left plain so it can converge.
            session.execute(
                select(ProviderAttemptDebitModel).where(
                    ProviderAttemptDebitModel.debit_id == record.debit_id
                )
            ).all()
            snapshot_open.set()
            assert winner_committed.wait(timeout=15), "winner never committed"
        return session

    loser._session_factory = priming_session_factory  # type: ignore[assignment]

    def run_loser() -> bool:
        return loser.hold_attempt_debit_unresolved(debit_id=record.debit_id, held_at=_T1)

    def run_winner() -> bool:
        assert snapshot_open.wait(timeout=15), "loser never opened its snapshot"
        settled = winner.settle_attempt_debit(
            debit_id=record.debit_id,
            budget_key=budget_key,
            basis="ACTUAL_USAGE",
            amount_usd=0.4,
            input_tokens=90,
            output_tokens=30,
            rate_card_ref="default-live-text",
            settled_at=_T1,
        )
        winner_committed.set()
        return settled

    with ThreadPoolExecutor(max_workers=2) as pool:
        loser_future = pool.submit(run_loser)
        winner_future = pool.submit(run_winner)
        winner_result = winner_future.result(timeout=30)
        loser_result = loser_future.result(timeout=30)

    # The conflict genuinely happened, by SQLSTATE and not by inference.
    assert "40001" in observed_sqlstates, (
        f"expected a serialization_failure (40001); observed {observed_sqlstates}"
    )
    # More than one session means the retry loop actually re-ran.
    assert sessions_opened["count"] >= 2
    assert winner_result is True
    # Converged, and honestly: the winner's settlement stands, and the
    # loser reports that it did not resolve the row - not an exception.
    assert loser_result is False
    row = winner.get_attempt_debit(debit_id=record.debit_id)
    budget = winner.get_budget_state(budget_key=budget_key)
    assert row is not None and budget is not None
    assert row.basis == "ACTUAL_USAGE"
    assert row.amount_usd == 0.4
    assert budget.current_spend_usd == 0.4
