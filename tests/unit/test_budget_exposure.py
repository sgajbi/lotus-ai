"""Unresolved billable exposure never releases hard admission capacity (issue #329).

Deep-audit F5 inverted: after a billable-risk failure WITHOUT usage evidence,
settlement used to release the reservation down to the ~4-bytes/token
heuristic - so a 1.50 USD hard limit could admit two 1.10 USD maxima. These
tests pin the closure: unknown usage HOLDS the reserved maximum
(``UNRESOLVED_MAX``), estimates are reporting posture only, and the sole
release path is the governed four-eyes reconciliation to a provider-evidenced
charge.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException

from app.config import settings
from app.contracts.model_catalogue import derive_candidate_identity_v2
from app.contracts.providers import (
    BudgetReconciliationApprovalRequest,
    BudgetReconciliationIntentRequest,
    ProviderFailureCategory,
)
from app.providers.base import ProviderExecutionError
from app.repositories.provider_operations_repository import ProviderAttemptDebitRecord
from app.services.budget_reconciliation import (
    approve_budget_reconciliation,
    request_budget_reconciliation,
)
from app.services.provider_budget_policy import (
    require_priceable_admission,
    reserve_attempt_spend,
    settle_attempt_spend,
    spent_for_execution,
)
from app.services.provider_operations_store import get_provider_operations_store
from app.services.provider_usage_accounting import AttemptDebit
from tests.support.governed_control import GOVERNED_APPROVER, GOVERNED_REQUESTER

_CANONICAL = derive_candidate_identity_v2(
    provider_id="text.openai",
    model_family="gpt-5.4",
    model_revision="gpt-5.4",
    deployment=None,
)


def _enforce(hard_limit: float) -> None:
    settings.live_text_budget_enforced = True
    settings.live_text_hard_budget_usd = hard_limit
    settings.live_text_input_cost_per_1k_tokens = 0.01
    settings.live_text_output_cost_per_1k_tokens = 0.03


def _debit(amount: float, *, basis: str = "CONSERVATIVE_ESTIMATE") -> AttemptDebit:
    return AttemptDebit(
        amount_usd=amount,
        basis=basis,  # type: ignore[arg-type]
        input_tokens=200,
        output_tokens=512,
        rate_card_ref="default-live-text",
    )


def _reserve(execution_id: str, amount: float, *, attempt_index: int = 0) -> str:
    return reserve_attempt_spend(
        execution_id=execution_id,
        candidate_entry_id="text.openai:gpt-5.4",
        provider_id="text.openai",
        model_revision="gpt-5.4",
        attempt_index=attempt_index,
        reservation=_debit(amount),
        candidate_id_v2=_CANONICAL,
    )


def _settle(
    execution_id: str,
    debit: AttemptDebit | None,
    *,
    attempt_index: int = 0,
    billable_risk: bool = True,
) -> bool:
    return settle_attempt_spend(
        execution_id=execution_id,
        candidate_entry_id="text.openai:gpt-5.4",
        attempt_index=attempt_index,
        debit=debit,
        candidate_id_v2=_CANONICAL,
        billable_risk=billable_risk,
    )


def _debit_id(execution_id: str, *, attempt_index: int = 0) -> str:
    return f"adbt2:{execution_id}:{_CANONICAL}:{attempt_index}"


def _counter() -> float:
    state = get_provider_operations_store().get_budget_state(budget_key="live_text_generation")
    return state.current_spend_usd if state is not None else 0.0


def test_unknown_usage_holds_the_reservation_and_the_next_maximum_is_refused() -> None:
    """The audit probe, inverted: reserve 1.10 against a 1.50 hard limit,
    settle a timeout's unknown usage - the counter keeps 1.10, the row is
    UNRESOLVED_MAX, and a second 1.10 maximum is REFUSED. Two admitted
    maxima can no longer jointly exceed the limit."""

    _enforce(1.50)
    assert _reserve("exec-a", 1.10) == "RESERVED"

    # Timeout/5xx/usage-withheld all reach settlement as an estimate debit.
    assert _settle("exec-a", _debit(0.35)) is True

    row = get_provider_operations_store().get_attempt_debit(debit_id=_debit_id("exec-a"))
    assert row is not None
    assert row.basis == "UNRESOLVED_MAX"
    assert row.amount_usd == 1.10
    assert _counter() == 1.10

    assert _reserve("exec-b", 1.10) == "REFUSED"
    # The exposure also counts against the caller's own execution ceiling,
    # so a retry or fallback admission sees the honest number.
    assert spent_for_execution("exec-a") == 1.10


def test_usage_evidence_and_proven_non_billability_still_release() -> None:
    """The hold is scoped to UNKNOWN usage: provider-reported usage settles
    down to the evidenced amount, and a proven non-billable attempt (429,
    pre-connect) releases to zero exactly as before."""

    _enforce(1.50)
    assert _reserve("exec-usage", 1.10) == "RESERVED"
    assert _settle("exec-usage", _debit(0.20, basis="ACTUAL_USAGE")) is True
    row = get_provider_operations_store().get_attempt_debit(debit_id=_debit_id("exec-usage"))
    assert row is not None
    assert row.basis == "ACTUAL_USAGE"
    assert _counter() == 0.20

    assert _reserve("exec-nobill", 1.10) == "RESERVED"
    assert _settle("exec-nobill", None, billable_risk=False) is True
    released = get_provider_operations_store().get_attempt_debit(debit_id=_debit_id("exec-nobill"))
    assert released is not None
    assert released.basis == "RELEASED"
    assert _counter() == 0.20


def test_holding_is_idempotent_and_a_second_resolution_is_a_noop() -> None:
    _enforce(1.50)
    assert _reserve("exec-idem", 1.10) == "RESERVED"
    assert _settle("exec-idem", _debit(0.35)) is True
    # Crash-retry of the same settlement converges without touching state.
    assert _settle("exec-idem", _debit(0.35)) is False
    # Late usage evidence cannot silently rewrite held exposure either: the
    # governed reconciliation is the only path off UNRESOLVED_MAX.
    assert _settle("exec-idem", _debit(0.20, basis="ACTUAL_USAGE")) is False
    assert _counter() == 1.10


def test_governed_reconciliation_is_the_only_release_and_it_takes_four_eyes() -> None:
    """Exposure settles to the provider-evidenced charge through the
    two-step governed action: distinct credentials, exact hash, counter
    released once, retry converges on the same evidenced outcome."""

    _enforce(1.50)
    assert _reserve("exec-rec", 1.10) == "RESERVED"
    assert _settle("exec-rec", _debit(0.35)) is True
    debit_id = _debit_id("exec-rec")

    pending = request_budget_reconciliation(
        BudgetReconciliationIntentRequest(
            debit_id=debit_id,
            evidenced_amount_usd=0.42,
            evidence_ref="invoice 2026-09/line 17",
        ),
        GOVERNED_REQUESTER,
    )

    # The requester's own credential cannot approve.
    with pytest.raises(HTTPException) as exc_info:
        approve_budget_reconciliation(
            BudgetReconciliationApprovalRequest(
                action_id=pending.governed_action.action_id,
                action_hash=pending.governed_action.action_hash,
            ),
            GOVERNED_REQUESTER,
        )
    assert exc_info.value.status_code == 403
    assert _counter() == 1.10

    approved = approve_budget_reconciliation(
        BudgetReconciliationApprovalRequest(
            action_id=pending.governed_action.action_id,
            action_hash=pending.governed_action.action_hash,
        ),
        GOVERNED_APPROVER,
    )
    assert approved.evidenced_amount_usd == 0.42
    assert approved.released_amount_usd == 0.68
    assert _counter() == 0.42
    row = get_provider_operations_store().get_attempt_debit(debit_id=debit_id)
    assert row is not None
    assert row.basis == "RECONCILED"
    assert row.amount_usd == 0.42

    # A lost response retried returns the SAME evidenced outcome - no second
    # release.
    replay = approve_budget_reconciliation(
        BudgetReconciliationApprovalRequest(
            action_id=pending.governed_action.action_id,
            action_hash=pending.governed_action.action_hash,
        ),
        GOVERNED_APPROVER,
    )
    assert replay.released_amount_usd == 0.68
    assert replay.governed_action.action_id == approved.governed_action.action_id
    assert _counter() == 0.42


def test_a_crash_orphaned_reservation_reconciles_too() -> None:
    """A crash before any settlement leaves RESERVED_MAX standing - the safe
    direction - and the same governed path resolves it to evidence."""

    _enforce(1.50)
    assert _reserve("exec-crash", 1.10) == "RESERVED"

    pending = request_budget_reconciliation(
        BudgetReconciliationIntentRequest(
            debit_id=_debit_id("exec-crash"),
            evidenced_amount_usd=0.0,
            evidence_ref="billing console: attempt never billed",
        ),
        GOVERNED_REQUESTER,
    )
    approved = approve_budget_reconciliation(
        BudgetReconciliationApprovalRequest(
            action_id=pending.governed_action.action_id,
            action_hash=pending.governed_action.action_hash,
        ),
        GOVERNED_APPROVER,
    )
    assert approved.released_amount_usd == 1.10
    assert _counter() == 0.0


def test_an_approval_reviewed_against_one_exposure_state_cannot_execute_another() -> None:
    """Freshness: the request pins the exposure's basis into the hash. If
    the row resolves by other means between request and approval, the
    rebuilt payload no longer matches and the approval refuses instead of
    double-releasing."""

    _enforce(1.50)
    assert _reserve("exec-fresh", 1.10) == "RESERVED"
    pending = request_budget_reconciliation(
        BudgetReconciliationIntentRequest(
            debit_id=_debit_id("exec-fresh"),
            evidenced_amount_usd=0.10,
            evidence_ref="invoice draft",
        ),
        GOVERNED_REQUESTER,
    )
    # Usage evidence arrives late and settles the crash-orphaned reservation.
    assert _settle("exec-fresh", _debit(0.20, basis="ACTUAL_USAGE")) is True
    assert _counter() == 0.20

    with pytest.raises(HTTPException) as exc_info:
        approve_budget_reconciliation(
            BudgetReconciliationApprovalRequest(
                action_id=pending.governed_action.action_id,
                action_hash=pending.governed_action.action_hash,
            ),
            GOVERNED_APPROVER,
        )
    assert exc_info.value.status_code == 409
    assert _counter() == 0.20


def test_reconciliation_requests_validate_the_exposure() -> None:
    _enforce(1.50)
    with pytest.raises(HTTPException) as missing:
        request_budget_reconciliation(
            BudgetReconciliationIntentRequest(
                debit_id="adbt2:absent:cand2_missing:0",
                evidenced_amount_usd=0.10,
                evidence_ref="nothing",
            ),
            GOVERNED_REQUESTER,
        )
    assert missing.value.status_code == 404

    assert _reserve("exec-settled", 1.10) == "RESERVED"
    assert _settle("exec-settled", _debit(0.20, basis="ACTUAL_USAGE")) is True
    with pytest.raises(HTTPException) as settled:
        request_budget_reconciliation(
            BudgetReconciliationIntentRequest(
                debit_id=_debit_id("exec-settled"),
                evidenced_amount_usd=0.10,
                evidence_ref="invoice",
            ),
            GOVERNED_REQUESTER,
        )
    assert settled.value.status_code == 409


def test_an_enforced_budget_that_cannot_price_the_attempt_fails_closed() -> None:
    """An unpriceable candidate under an enforced hard budget must refuse
    admission, not bypass the limit by reserving nothing."""

    settings.live_text_budget_enforced = True
    settings.live_text_hard_budget_usd = 1.50
    with pytest.raises(ProviderExecutionError) as exc_info:
        require_priceable_admission(None)
    assert exc_info.value.category is ProviderFailureCategory.INVALID_BUDGET_CONFIGURATION

    settings.live_text_budget_enforced = False
    require_priceable_admission(None)
    require_priceable_admission(_debit(0.10))


def test_sql_concurrent_reconciliation_releases_exactly_once(tmp_path: Path) -> None:
    """Two replicas approving reconciliation of the same exposure: the
    guarded basis+amount compare-and-set lets exactly one adjust the
    counter."""

    from app.repositories.sqlalchemy_provider_operations_repository import (
        SqlAlchemyProviderOperationsRepository,
    )
    from tests.support.migration_runner import upgrade_database_to_head

    database_url = f"sqlite:///{tmp_path / 'lotus-ai-exposure.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyProviderOperationsRepository(database_url)

    record = ProviderAttemptDebitRecord(
        debit_id="adbt2:exec-sql:cand2_x:0",
        provider_id="text.openai",
        basis="RESERVED_MAX",
        amount_usd=1.10,
        input_tokens=200,
        output_tokens=512,
        rate_card_ref="default-live-text",
        recorded_at="2026-09-05T00:00:00Z",
        candidate_entry_id="text.openai:gpt-5.4",
        model_revision="gpt-5.4",
        attempt_index=0,
    )
    assert (
        repository.reserve_attempt_debit(
            record, budget_key="live_text_generation", hard_limit_usd=None
        )
        == "RESERVED"
    )
    assert (
        repository.hold_attempt_debit_unresolved(
            debit_id=record.debit_id, held_at="2026-09-05T00:00:01Z"
        )
        is True
    )
    # Idempotent: a crash-retry of the hold is a no-op.
    assert (
        repository.hold_attempt_debit_unresolved(
            debit_id=record.debit_id, held_at="2026-09-05T00:00:02Z"
        )
        is False
    )

    def _reconcile(session_tag: str) -> bool:
        own = SqlAlchemyProviderOperationsRepository(database_url)
        return own.reconcile_attempt_debit(
            debit_id=record.debit_id,
            budget_key="live_text_generation",
            amount_usd=0.42,
            input_tokens=100,
            output_tokens=40,
            rate_card_ref="default-live-text",
            reconciled_at=f"2026-09-05T00:00:03Z+{session_tag}",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(_reconcile, ["a", "b"]))
    assert sorted(outcomes) == [False, True]
    # A reconciliation arriving AFTER resolution refuses deterministically
    # at the basis check, and a missing row reads as absent, not an error.
    assert _reconcile("late") is False
    assert repository.get_attempt_debit(debit_id="adbt2:absent:cand2_none:0") is None

    budget = repository.get_budget_state(budget_key="live_text_generation")
    assert budget is not None
    assert budget.current_spend_usd == 0.42
    row = repository.get_attempt_debit(debit_id=record.debit_id)
    assert row is not None
    assert row.basis == "RECONCILED"


def test_a_served_response_with_usage_withheld_holds_its_maximum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Usage-missing SUCCESS is the same unknown: the served attempt's row
    holds the reserved maximum while the response honestly reports what it
    can."""

    from tests.unit.test_attempt_billing import (
        _Response,
        _debit_key,
        _run_transport,
        _seed_cost_scalars,
    )

    _seed_cost_scalars()
    body = b'{"id": "resp_nousage", "model": "gpt-5.4", "output_text": "OK"}'
    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: _Response(body))

    response = _run_transport(retry_limit=0, execution_id="exec-withheld")
    assert response.failure_category is None
    # The provider withheld usage: the response can honestly report none.
    assert response.output_tokens is None

    row = get_provider_operations_store().get_attempt_debit(debit_id=_debit_key("exec-withheld", 0))
    assert row is not None
    assert row.basis == "UNRESOLVED_MAX"
    assert _counter() == row.amount_usd


def test_an_exposure_resolved_mid_execution_applies_no_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The narrow race between the claim and the counter release: if the
    guarded reconcile CAS loses (the row left its held basis after the
    freshness rebuild), the approval refuses and no release is applied."""

    _enforce(1.50)
    assert _reserve("exec-race", 1.10) == "RESERVED"
    assert _settle("exec-race", _debit(0.35)) is True
    pending = request_budget_reconciliation(
        BudgetReconciliationIntentRequest(
            debit_id=_debit_id("exec-race"),
            evidenced_amount_usd=0.42,
            evidence_ref="invoice",
        ),
        GOVERNED_REQUESTER,
    )

    import app.services.budget_reconciliation as reconciliation_module

    monkeypatch.setattr(reconciliation_module, "reconcile_attempt_spend", lambda **kwargs: False)
    with pytest.raises(HTTPException) as exc_info:
        approve_budget_reconciliation(
            BudgetReconciliationApprovalRequest(
                action_id=pending.governed_action.action_id,
                action_hash=pending.governed_action.action_hash,
            ),
            GOVERNED_APPROVER,
        )
    assert exc_info.value.status_code == 409
    assert "no release was applied" in exc_info.value.detail
    assert _counter() == 1.10


def test_a_crash_between_release_and_evidence_recovers_the_true_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Crash after the counter released but before EXECUTED evidence wrote:
    the claiming credential resumes through the PUBLIC contract field, the
    guarded reconcile converges as a no-op, and the replayed response
    reports the TRUE released difference from the hash-pinned held amount -
    with the counter adjusted exactly once."""

    _enforce(1.50)
    assert _reserve("exec-resume", 1.10) == "RESERVED"
    assert _settle("exec-resume", _debit(0.35)) is True
    pending = request_budget_reconciliation(
        BudgetReconciliationIntentRequest(
            debit_id=_debit_id("exec-resume"),
            evidenced_amount_usd=0.42,
            evidence_ref="invoice",
        ),
        GOVERNED_REQUESTER,
    )

    store = get_provider_operations_store()
    real_transition = store.transition_governed_action
    from app.contracts.governed_actions import GovernedActionRecord, GovernedActionStatus

    def crash_before_evidence(
        *,
        action_id: str,
        expected_status: str,
        record: GovernedActionRecord,
        expected_claimed_at: str | None = None,
    ) -> bool:
        if expected_status == GovernedActionStatus.CLAIMED.value:
            return False
        return real_transition(
            action_id=action_id,
            expected_status=expected_status,
            record=record,
            expected_claimed_at=expected_claimed_at,
        )

    monkeypatch.setattr(store, "transition_governed_action", crash_before_evidence)
    with pytest.raises(HTTPException) as exc_info:
        approve_budget_reconciliation(
            BudgetReconciliationApprovalRequest(
                action_id=pending.governed_action.action_id,
                action_hash=pending.governed_action.action_hash,
            ),
            GOVERNED_APPROVER,
        )
    assert exc_info.value.status_code == 409
    # The release already happened; the evidence write did not.
    assert _counter() == 0.42

    monkeypatch.setattr(store, "transition_governed_action", real_transition)
    recovered = approve_budget_reconciliation(
        BudgetReconciliationApprovalRequest(
            action_id=pending.governed_action.action_id,
            action_hash=pending.governed_action.action_hash,
            resume_interrupted_claim=True,
        ),
        GOVERNED_APPROVER,
    )
    assert recovered.evidenced_amount_usd == 0.42
    assert recovered.released_amount_usd == 0.68
    assert recovered.governed_action.status is GovernedActionStatus.EXECUTED
    # Released exactly once.
    assert _counter() == 0.42


def test_unpriceable_billable_exposure_holds_with_provenance_intact() -> None:
    """Issue #346: the rate card expiring between admission and settlement
    must not release the reservation - debit-None has TWO producers, and
    only stated non-billability releases. The held row keeps the
    reservation's provenance (tokens, rate_card_ref) for reconciliation."""

    _enforce(1.50)
    assert _reserve("exec-expiry", 1.10) == "RESERVED"

    # Timeout/5xx after the card expired: pricing returns None, risk stands.
    assert _settle("exec-expiry", None, billable_risk=True) is True
    row = get_provider_operations_store().get_attempt_debit(debit_id=_debit_id("exec-expiry"))
    assert row is not None
    assert row.basis == "UNRESOLVED_MAX"
    assert row.amount_usd == 1.10
    assert row.input_tokens == 200
    assert row.output_tokens == 512
    assert row.rate_card_ref == "default-live-text"
    assert _counter() == 1.10

    # The audit reproduction inverted: the next 1.10 maximum is REFUSED and
    # the caller's execution ceiling sees the held exposure.
    assert _reserve("exec-expiry-b", 1.10) == "REFUSED"
    assert spent_for_execution("exec-expiry") == 1.10

    # Replay without double adjustment: the second settle is a no-op.
    assert _settle("exec-expiry", None, billable_risk=True) is False
    assert _counter() == 1.10

    # Governed reconciliation restores headroom exactly once.
    pending = request_budget_reconciliation(
        BudgetReconciliationIntentRequest(
            debit_id=_debit_id("exec-expiry"),
            evidenced_amount_usd=0.30,
            evidence_ref="invoice after card renewal",
        ),
        GOVERNED_REQUESTER,
    )
    approved = approve_budget_reconciliation(
        BudgetReconciliationApprovalRequest(
            action_id=pending.governed_action.action_id,
            action_hash=pending.governed_action.action_hash,
        ),
        GOVERNED_APPROVER,
    )
    assert approved.released_amount_usd == 0.80
    assert _counter() == 0.30
    replay = approve_budget_reconciliation(
        BudgetReconciliationApprovalRequest(
            action_id=pending.governed_action.action_id,
            action_hash=pending.governed_action.action_hash,
        ),
        GOVERNED_APPROVER,
    )
    assert replay.released_amount_usd == 0.80
    assert _counter() == 0.30


def test_rate_expiry_during_a_served_response_holds_and_logs_usage(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Issue #346, the decision stated: provider-reported usage WITHOUT an
    effective rate card is not an evidenced amount - the served attempt
    holds its reserved maximum, and the observed usage is logged as
    reconciliation input evidence."""

    from tests.unit.test_attempt_billing import (
        _Response,
        _SUCCESS_BODY,
        _debit_key,
        _run_transport,
        _seed_cost_scalars,
    )
    import app.services.provider_usage_accounting as accounting

    _seed_cost_scalars()
    real_estimate = accounting.estimate_live_text_cost
    calls = {"count": 0}

    def _expiring_estimate(**kwargs: Any) -> Any:
        calls["count"] += 1
        if calls["count"] > 1:
            # The card expired after admission priced the reservation.
            return accounting.UNKNOWN_COST
        return real_estimate(**kwargs)

    monkeypatch.setattr(accounting, "estimate_live_text_cost", _expiring_estimate)
    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: _Response(_SUCCESS_BODY))

    import logging

    with caplog.at_level(logging.INFO, logger="app.provider"):
        response = _run_transport(retry_limit=0, execution_id="exec-served-expiry")
    assert response.failure_category is None
    # The observed usage rides operator evidence for reconciliation.
    assert any(
        "attempt_exposure_held_unpriceable" in record.getMessage() for record in caplog.records
    )

    row = get_provider_operations_store().get_attempt_debit(
        debit_id=_debit_key("exec-served-expiry", 0)
    )
    assert row is not None
    assert row.basis == "UNRESOLVED_MAX"
    # Reservation provenance, not the served usage: the held amount is the
    # admitted maximum and its tokens are the reservation's bounds.
    assert row.output_tokens == 512
