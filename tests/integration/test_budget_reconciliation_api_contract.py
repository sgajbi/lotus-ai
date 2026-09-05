"""API contract for governed budget reconciliation (issue #329).

The unit suite proves the hold/release semantics; this contract proves the
HTTP wiring: verified-credential enforcement on both routes, the pending step
releasing nothing, the distinct-credential approval settling the exposure to
the evidenced charge, and an unknown action refusing with 404.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.contracts.model_catalogue import derive_candidate_identity_v2
from app.services.provider_budget_policy import (
    reserve_attempt_spend,
    settle_attempt_spend,
)
from app.services.provider_operations_store import get_provider_operations_store
from app.services.provider_usage_accounting import AttemptDebit
from tests.support.caller_credentials import (
    generate_caller_signing_key,
    mint_caller_credential,
    public_keys_setting,
)

_REQUESTER_KEY = generate_caller_signing_key()
_APPROVER_KEY = generate_caller_signing_key()
_PUBLIC_KEYS = public_keys_setting(
    **{"budget-ops-alpha": _REQUESTER_KEY, "budget-ops-beta": _APPROVER_KEY}
)
_REQUESTER_HEADERS = {
    "Authorization": "Bearer "
    + mint_caller_credential(
        signing_key=_REQUESTER_KEY,
        key_id="budget-ops-alpha",
        subject="lotus-platform",
        expires_in_seconds=3600,
    )
}
_APPROVER_HEADERS = {
    "Authorization": "Bearer "
    + mint_caller_credential(
        signing_key=_APPROVER_KEY,
        key_id="budget-ops-beta",
        subject="lotus-platform",
        expires_in_seconds=3600,
    )
}

_CANONICAL = derive_candidate_identity_v2(
    provider_id="text.openai",
    model_family="gpt-5.4",
    model_revision="gpt-5.4",
    deployment=None,
)


def _seed_unresolved_exposure() -> str:
    """One held reservation on the books, exactly as a timeout leaves it."""

    settings.live_text_budget_enforced = True
    settings.live_text_hard_budget_usd = 1.50
    settings.live_text_input_cost_per_1k_tokens = 0.01
    settings.live_text_output_cost_per_1k_tokens = 0.03
    debit = AttemptDebit(
        amount_usd=1.10,
        basis="CONSERVATIVE_ESTIMATE",
        input_tokens=200,
        output_tokens=512,
        rate_card_ref="default-live-text",
    )
    reserved = reserve_attempt_spend(
        execution_id="exec-api-rec",
        candidate_entry_id="text.openai:gpt-5.4",
        provider_id="text.openai",
        model_revision="gpt-5.4",
        attempt_index=0,
        reservation=debit,
        candidate_id_v2=_CANONICAL,
    )
    assert reserved == "RESERVED"
    assert (
        settle_attempt_spend(
            execution_id="exec-api-rec",
            candidate_entry_id="text.openai:gpt-5.4",
            attempt_index=0,
            debit=AttemptDebit(
                amount_usd=0.35,
                basis="CONSERVATIVE_ESTIMATE",
                input_tokens=50,
                output_tokens=512,
                rate_card_ref="default-live-text",
            ),
            candidate_id_v2=_CANONICAL,
        )
        is True
    )
    return f"adbt2:exec-api-rec:{_CANONICAL}:0"


def _configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "caller_trust_mode", "verified_service_jwt")
    monkeypatch.setattr(settings, "caller_jwt_issuer", "https://platform.lotus/issuer")
    monkeypatch.setattr(settings, "caller_jwt_audience", "lotus-ai")
    monkeypatch.setattr(settings, "caller_jwt_public_keys", _PUBLIC_KEYS)


def test_reconciliation_routes_execute_the_governed_flow(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure(monkeypatch)
    debit_id = _seed_unresolved_exposure()

    unverified = client.post(
        "/platform/provider-budget/reconciliation-requests",
        json={
            "debit_id": debit_id,
            "evidenced_amount_usd": 0.42,
            "evidence_ref": "invoice 2026-09/line 17",
        },
    )
    assert unverified.status_code == 401

    pending = client.post(
        "/platform/provider-budget/reconciliation-requests",
        json={
            "debit_id": debit_id,
            "evidenced_amount_usd": 0.42,
            "evidence_ref": "invoice 2026-09/line 17",
            "requested_by": "ops.user@lotus",
        },
        headers=_REQUESTER_HEADERS,
    )
    assert pending.status_code == 200
    action = pending.json()["governed_action"]
    assert action["status"] == "PENDING"
    # The pending step releases nothing.
    state = get_provider_operations_store().get_budget_state(budget_key="live_text_generation")
    assert state is not None
    assert state.current_spend_usd == 1.10

    unknown = client.post(
        "/platform/provider-budget/reconciliation-approvals",
        json={"action_id": "gact_does_not_exist", "action_hash": "0" * 64},
        headers=_APPROVER_HEADERS,
    )
    assert unknown.status_code == 404

    approved = client.post(
        "/platform/provider-budget/reconciliation-approvals",
        json={"action_id": action["action_id"], "action_hash": action["action_hash"]},
        headers=_APPROVER_HEADERS,
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body["evidenced_amount_usd"] == 0.42
    assert body["released_amount_usd"] == 0.68
    assert body["governed_action"]["status"] == "EXECUTED"

    state = get_provider_operations_store().get_budget_state(budget_key="live_text_generation")
    assert state is not None
    assert state.current_spend_usd == 0.42
    row = get_provider_operations_store().get_attempt_debit(debit_id=debit_id)
    assert row is not None
    assert row.basis == "RECONCILED"
