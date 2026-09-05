"""One approved intent executes at most once, and destructive work is
recoverable (issue #327, audit F2+F3).

The atomic PENDING->CLAIMED transition is the single ownership authority:
concurrent approvals cannot both run the effect, supersession cannot race an
execution, an interrupted claim is resumable only by its owner, and an
erasure whose receipt was lost is retrievable from durable results without
re-erasing.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, BrokenBarrierError

import pytest
from fastapi import HTTPException

from app.contracts.governed_actions import (
    GovernedActionRecord,
    GovernedActionStatus,
    GovernedActionType,
)
from app.services.governed_action_control import (
    approve_and_execute_governed_action,
    submit_governed_action,
)
from app.services.provider_operations_store import get_provider_operations_store
from tests.support.governed_control import GOVERNED_APPROVER, GOVERNED_REQUESTER

_PAYLOAD: dict[str, str | None] = {
    "action_type": GovernedActionType.PROVIDER_OPERATIONS_RESET.value,
    "target": "live",
}


def _submit() -> object:
    return submit_governed_action(
        caller=GOVERNED_REQUESTER,
        action_type=GovernedActionType.PROVIDER_OPERATIONS_RESET,
        target="live",
        payload=dict(_PAYLOAD),
        attribution=None,
    )


def _approve(record: object, execute: object, *, resume_interrupted_claim: bool = False) -> object:
    return approve_and_execute_governed_action(
        caller=GOVERNED_APPROVER,
        action_id=record.action_id,  # type: ignore[attr-defined]
        expected_target="live",
        expected_hash=record.action_hash,  # type: ignore[attr-defined]
        current_payload_builder=lambda pending: dict(pending.action_payload),
        attribution=None,
        execute=execute,  # type: ignore[arg-type]
        resume_interrupted_claim=resume_interrupted_claim,
    )


def test_concurrent_approvals_execute_the_effect_exactly_once() -> None:
    """The audit probe, inverted: two simultaneous approvals raced the old
    read-check-execute flow into two domain effects. The atomic claim admits
    exactly one; the loser is a bounded 409, never a second effect."""

    pending = _submit()
    barrier = Barrier(2, timeout=2)
    effects: list[str] = []

    def _effect(record: object) -> None:
        try:
            # Only ONE approval may reach the effect now; the barrier that
            # proved the race in the audit probe must therefore time out.
            barrier.wait()
        except BrokenBarrierError:
            pass
        effects.append(record.action_id)  # type: ignore[attr-defined]

    outcomes: list[object] = []

    def _attempt(_: int) -> None:
        try:
            outcomes.append(_approve(pending, _effect))
        except HTTPException as exc:
            outcomes.append(exc.status_code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(_attempt, range(2)))

    assert len(effects) == 1
    assert sorted(o if isinstance(o, int) else 0 for o in outcomes) == [0, 409]
    stored = get_provider_operations_store().get_governed_action(
        pending.action_id  # type: ignore[attr-defined]
    )
    assert stored is not None
    assert stored.status is GovernedActionStatus.EXECUTED


def test_supersession_cannot_race_a_claimed_execution() -> None:
    """Submitting a replacement intent while the prior action is mid-execution
    must not un-claim it: the guarded supersession loses and the executed
    action's evidence stands, while the new intent records as PENDING."""

    first = _submit()
    replacement_holder: dict[str, object] = {}

    def _effect_and_supersede(record: object) -> None:
        # A concurrent submission arrives while the effect is running.
        replacement_holder["record"] = _submit()

    executed = _approve(first, _effect_and_supersede)
    assert executed.status is GovernedActionStatus.EXECUTED  # type: ignore[attr-defined]

    store = get_provider_operations_store()
    stored_first = store.get_governed_action(first.action_id)  # type: ignore[attr-defined]
    assert stored_first is not None
    assert stored_first.status is GovernedActionStatus.EXECUTED
    assert stored_first.superseded_by_action_id is None
    replacement = replacement_holder["record"]
    stored_second = store.get_governed_action(replacement.action_id)  # type: ignore[attr-defined]
    assert stored_second is not None
    assert stored_second.status is GovernedActionStatus.PENDING


def test_a_stale_approval_after_supersession_is_refused() -> None:
    first = _submit()
    second = _submit()
    assert second.action_id != first.action_id  # type: ignore[attr-defined]

    with pytest.raises(HTTPException) as exc_info:
        _approve(first, lambda record: None)
    assert exc_info.value.status_code == 409

    stored = get_provider_operations_store().get_governed_action(
        first.action_id  # type: ignore[attr-defined]
    )
    assert stored is not None
    assert stored.status is GovernedActionStatus.SUPERSEDED


def test_crash_after_effect_recovers_to_one_logical_outcome() -> None:
    """A process death between the effect and the EXECUTED write leaves a
    CLAIMED action whose effect already happened. The claiming credential's
    retry re-invokes the callback - idempotent under the action identity per
    the documented contract - and finalizes with one logical outcome."""

    pending = _submit()
    performed: set[str] = set()

    def _idempotent_effect_then_crash(record: object) -> None:
        performed.add(record.action_id)  # type: ignore[attr-defined]
        raise RuntimeError("process died before the EXECUTED write")

    with pytest.raises(RuntimeError):
        _approve(pending, _idempotent_effect_then_crash)
    assert performed == {pending.action_id}  # type: ignore[attr-defined]

    executed = approve_and_execute_governed_action(
        caller=GOVERNED_APPROVER,
        action_id=pending.action_id,  # type: ignore[attr-defined]
        expected_target="live",
        expected_hash=pending.action_hash,  # type: ignore[attr-defined]
        current_payload_builder=lambda record: dict(record.action_payload),
        attribution=None,
        execute=lambda record: performed.add(record.action_id),
        resume_interrupted_claim=True,
    )
    assert executed.status is GovernedActionStatus.EXECUTED
    assert performed == {pending.action_id}  # type: ignore[attr-defined]
    assert executed.requester_key_id == GOVERNED_REQUESTER.credential_key_id
    assert executed.approver_key_id == GOVERNED_APPROVER.credential_key_id
    assert executed.action_hash == pending.action_hash  # type: ignore[attr-defined]


def test_sql_claim_is_a_guarded_single_winner_across_sessions(tmp_path: Path) -> None:
    """Two INDEPENDENT SQL sessions (separate repository instances on one
    database) race the same PENDING action: the guarded UPDATE admits exactly
    one claim; the other returns False without writing."""

    from app.repositories.sqlalchemy_provider_operations_repository import (
        SqlAlchemyProviderOperationsRepository,
    )
    from tests.support.migration_runner import upgrade_database_to_head

    database_url = f"sqlite:///{tmp_path / 'governed-claims.db'}"
    upgrade_database_to_head(database_url)
    session_a = SqlAlchemyProviderOperationsRepository(database_url)
    session_b = SqlAlchemyProviderOperationsRepository(database_url)

    from app.contracts.governed_actions import (
        GovernedActionRecord,
        GovernedActorClass,
    )

    pending = GovernedActionRecord(
        action_id="gact_sql_claim_race",
        action_type=GovernedActionType.PROVIDER_OPERATIONS_RESET,
        actor_class=GovernedActorClass.HUMAN_APPROVED,
        status=GovernedActionStatus.PENDING,
        target="live",
        action_hash="a" * 64,
        action_payload=dict(_PAYLOAD),
        requester_caller_app="operator-service",
        requester_trust_source="verified_service_jwt",
        requester_key_id="key-a",
        requested_at="2026-09-05T00:00:00Z",
    )
    session_a.upsert_governed_action(pending)
    claim_a = pending.model_copy(
        update={"status": GovernedActionStatus.CLAIMED, "approver_key_id": "key-b"}
    )
    claim_b = pending.model_copy(
        update={"status": GovernedActionStatus.CLAIMED, "approver_key_id": "key-c"}
    )

    won_a = session_a.transition_governed_action(
        action_id=pending.action_id,
        expected_status=GovernedActionStatus.PENDING.value,
        record=claim_a,
    )
    won_b = session_b.transition_governed_action(
        action_id=pending.action_id,
        expected_status=GovernedActionStatus.PENDING.value,
        record=claim_b,
    )

    assert (won_a, won_b) == (True, False)
    stored = session_b.get_governed_action(pending.action_id)
    assert stored is not None
    assert stored.status is GovernedActionStatus.CLAIMED
    assert stored.approver_key_id == "key-b"

    # The resume/finalize/release fence, cross-session: both sessions hold
    # the SAME stale claim instant; the guarded UPDATE on (status,
    # claimed_at) admits exactly one rotation, and a finalization fenced to
    # the stale instant loses to the rotated one. (SQLite here; the guarded
    # single-statement UPDATE is backend-generic - PostgreSQL applies the
    # same row-level atomicity.)
    with_claim = claim_a.model_copy(update={"claimed_at": "2026-09-05T00:01:00Z"})
    session_a.upsert_governed_action(with_claim)
    rotate_a = with_claim.model_copy(update={"claimed_at": "2026-09-05T00:02:00Z"})
    rotate_b = with_claim.model_copy(update={"claimed_at": "2026-09-05T00:02:01Z"})
    rotated_a = session_a.transition_governed_action(
        action_id=pending.action_id,
        expected_status=GovernedActionStatus.CLAIMED.value,
        record=rotate_a,
        expected_claimed_at="2026-09-05T00:01:00Z",
    )
    rotated_b = session_b.transition_governed_action(
        action_id=pending.action_id,
        expected_status=GovernedActionStatus.CLAIMED.value,
        record=rotate_b,
        expected_claimed_at="2026-09-05T00:01:00Z",
    )
    assert (rotated_a, rotated_b) == (True, False)

    stale_finalize = session_b.transition_governed_action(
        action_id=pending.action_id,
        expected_status=GovernedActionStatus.CLAIMED.value,
        record=with_claim.model_copy(update={"status": GovernedActionStatus.EXECUTED}),
        expected_claimed_at="2026-09-05T00:01:00Z",
    )
    owned_finalize = session_a.transition_governed_action(
        action_id=pending.action_id,
        expected_status=GovernedActionStatus.CLAIMED.value,
        record=rotate_a.model_copy(update={"status": GovernedActionStatus.EXECUTED}),
        expected_claimed_at="2026-09-05T00:02:00Z",
    )
    assert (stale_finalize, owned_finalize) == (False, True)


def test_concurrent_resumes_take_exclusive_ownership_before_effects() -> None:
    """The resume-side variant of the two-owner window: credential identity
    does not prove the original executor stopped, so resuming must acquire
    exclusive execution ownership by CAS BEFORE effects run - exactly one
    resumer enters the callback, the loser refuses with 409, and exactly one
    EXECUTED evidence write exists."""

    pending = _submit()

    def _explode(record: object) -> None:
        raise RuntimeError("first execution died")

    with pytest.raises(RuntimeError):
        _approve(pending, execute=_explode)
    claimed = get_provider_operations_store().get_governed_action(
        pending.action_id  # type: ignore[attr-defined]
    )
    assert claimed is not None
    assert claimed.status is GovernedActionStatus.CLAIMED

    entries: list[str] = []
    outcomes: list[object] = []
    store = get_provider_operations_store()
    real_get = store.get_governed_action
    # Both resumers must READ THE SAME stale claim instant before either
    # rotates it - the exact interleaving the audit probe drove. The gated
    # read guarantees the race reaches the compare-and-set.
    read_together = Barrier(2, timeout=5)

    def _gated_get(action_id: str) -> GovernedActionRecord | None:
        result = real_get(action_id)
        if result is not None and result.status is GovernedActionStatus.CLAIMED:
            try:
                read_together.wait()
            except BrokenBarrierError:
                pass
        return result

    store.get_governed_action = _gated_get  # type: ignore[method-assign]
    try:

        def _resume() -> None:
            try:
                outcomes.append(
                    _approve(
                        pending,
                        execute=lambda record: entries.append(record.action_id),
                        resume_interrupted_claim=True,
                    )
                )
            except HTTPException as exc:
                outcomes.append(exc.status_code)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(_resume), pool.submit(_resume)]
            for future in futures:
                future.result()
    finally:
        store.get_governed_action = real_get  # type: ignore[method-assign]

    # Exclusive ownership BEFORE effects: one entry, not two - the loser is
    # refused at the rotation compare-and-set, never after its effect.
    assert entries == [pending.action_id]  # type: ignore[attr-defined]
    assert sorted(x for x in outcomes if isinstance(x, int)) == [409]
    final = real_get(pending.action_id)  # type: ignore[attr-defined]
    assert final is not None
    assert final.status is GovernedActionStatus.EXECUTED


def test_resume_versus_a_still_running_executor_yields_one_evidence_write() -> None:
    """A resumer cannot know whether the prior executor died or is merely
    slow. Taking over a live claim is therefore LEGAL - the rotation fence
    guarantees what matters: the superseded executor's finalization loses
    (409 after its effect), the taker's lands, the callback stays idempotent
    under the action identity, and exactly one evidence write exists."""

    from threading import Event

    pending = _submit()

    def _explode(record: object) -> None:
        raise RuntimeError("first execution died")

    with pytest.raises(RuntimeError):
        _approve(pending, execute=_explode)

    performed: set[str] = set()
    first_entered = Event()
    release_first = Event()
    first_outcome: list[object] = []

    def _slow_idempotent_effect(record: object) -> None:
        performed.add(record.action_id)  # type: ignore[attr-defined]
        first_entered.set()
        release_first.wait(timeout=5)

    def _first_resume() -> None:
        try:
            first_outcome.append(
                _approve(pending, execute=_slow_idempotent_effect, resume_interrupted_claim=True)
            )
        except HTTPException as exc:
            first_outcome.append(exc.status_code)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_first_resume)
        assert first_entered.wait(timeout=5)
        # The takeover: a second resume by the owner credential, reading the
        # FRESH instant, rotates it and completes while the first executor
        # is still running.
        taken_over = _approve(
            pending,
            execute=lambda record: performed.add(record.action_id),
            resume_interrupted_claim=True,
        )
        release_first.set()
        future.result()

    assert taken_over.status is GovernedActionStatus.EXECUTED  # type: ignore[attr-defined]
    # The superseded executor ran its (idempotent) effect but could NOT
    # stamp evidence over the taker's ownership.
    assert first_outcome == [409]
    assert performed == {pending.action_id}  # type: ignore[attr-defined]
    final = get_provider_operations_store().get_governed_action(
        pending.action_id  # type: ignore[attr-defined]
    )
    assert final is not None
    assert final.status is GovernedActionStatus.EXECUTED
    assert final.executed_at == taken_over.executed_at  # type: ignore[attr-defined]
