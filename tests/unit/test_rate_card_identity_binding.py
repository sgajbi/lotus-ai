"""Accounting binds the rate-card catalogue by routed identity (issue #178, S2)."""

from fastapi import HTTPException
from pytest import raises

from app.contracts.rate_cards import RateCard, RateCardScopeKind
from app.services.provider_usage_accounting import (
    estimate_embedding_cost,
    estimate_live_text_cost,
    resolve_effective_live_text_card,
    save_rate_card,
)


def _card(
    card_id: str,
    *,
    scope_kind: RateCardScopeKind = RateCardScopeKind.DEFAULT_LIVE_TEXT,
    scope_target: str | None = None,
    input_rate: float = 0.01,
    output_rate: float = 0.03,
    effective_from: str | None = None,
    effective_to: str | None = None,
) -> RateCard:
    return RateCard(
        card_id=card_id,
        scope_kind=scope_kind,
        scope_target=scope_target,
        currency="USD",
        input_cost_per_1k_tokens=input_rate,
        output_cost_per_1k_tokens=output_rate,
        effective_from_utc=effective_from,
        effective_to_utc=effective_to,
        created_at="2026-08-31T00:00:00Z",
        last_updated_at="2026-08-31T00:00:00Z",
    )


def test_model_scoped_card_beats_the_default_and_records_its_ref() -> None:
    save_rate_card(_card("default"))
    save_rate_card(
        _card(
            "premium-model",
            scope_kind=RateCardScopeKind.MODEL_REVISION,
            scope_target="gpt-5.4-2026-06-01",
            input_rate=0.10,
            output_rate=0.30,
        )
    )

    premium = estimate_live_text_cost(
        input_tokens=1000, output_tokens=1000, model_revision="gpt-5.4-2026-06-01"
    )
    assert premium.rate_card_ref == "premium-model"
    assert premium.estimated_cost_usd == 0.40
    assert premium.cost_posture == "ESTIMATED"

    # Two catalogued models with different rates price correctly in the same
    # process lifetime - the global-scalar model could not do this.
    other = estimate_live_text_cost(
        input_tokens=1000, output_tokens=1000, model_revision="qwen3:8b"
    )
    assert other.rate_card_ref == "default"
    assert other.estimated_cost_usd == 0.04


def test_new_effective_row_changes_costs_only_after_its_instant() -> None:
    save_rate_card(_card("old-prices", effective_to="2026-09-01T00:00:00Z"))
    save_rate_card(
        _card(
            "new-prices",
            input_rate=0.02,
            output_rate=0.06,
            effective_from="2026-09-01T00:00:00Z",
        )
    )

    before = estimate_live_text_cost(
        input_tokens=1000, output_tokens=1000, at_utc="2026-08-31T23:59:59Z"
    )
    after = estimate_live_text_cost(
        input_tokens=1000, output_tokens=1000, at_utc="2026-09-01T00:00:00Z"
    )
    assert before.rate_card_ref == "old-prices"
    assert before.estimated_cost_usd == 0.04
    assert after.rate_card_ref == "new-prices"
    assert after.estimated_cost_usd == 0.08


def test_overlapping_effective_ranges_are_refused_at_write() -> None:
    save_rate_card(_card("open-ended"))

    with raises(HTTPException) as exc_info:
        save_rate_card(_card("competing", input_rate=0.02))
    assert exc_info.value.status_code == 409
    assert "overlaps" in str(exc_info.value.detail)

    # A different scope key never conflicts.
    save_rate_card(
        _card(
            "scoped",
            scope_kind=RateCardScopeKind.MODEL_REVISION,
            scope_target="gpt-5.4",
            input_rate=0.02,
        )
    )
    # Replacing a card under its own id is always allowed.
    save_rate_card(_card("open-ended", input_rate=0.05))


def test_missing_card_is_an_explicit_cost_unknown_posture() -> None:
    estimate = estimate_live_text_cost(input_tokens=100, output_tokens=100)
    assert estimate.estimated_cost_usd is None
    assert estimate.rate_card_ref is None
    assert estimate.cost_posture == "UNKNOWN"
    assert resolve_effective_live_text_card() is None


def test_embedding_executions_price_through_their_own_scope() -> None:
    assert estimate_embedding_cost(input_tokens=1000).cost_posture == "UNKNOWN"

    save_rate_card(
        _card(
            "embedding-default",
            scope_kind=RateCardScopeKind.EMBEDDING_DEFAULT,
            input_rate=0.001,
            output_rate=0.0,
        )
    )

    estimate = estimate_embedding_cost(input_tokens=2000)
    assert estimate.rate_card_ref == "embedding-default"
    assert estimate.estimated_cost_usd == 0.002


def test_scope_target_validation_is_enforced_by_the_contract() -> None:
    with raises(ValueError):
        _card("bad", scope_kind=RateCardScopeKind.MODEL_REVISION, scope_target=None)
    with raises(ValueError):
        _card("bad2", scope_target="unexpected")
