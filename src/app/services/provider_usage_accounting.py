"""Live-text cost accounting, sourced from the rate-card catalogue (issue #178).

The two legacy cost scalars are seed inputs only: the seed migrates them into
the DEFAULT_LIVE_TEXT rate card, and estimation resolves the effective card.
Behaviour is cutover-identical - the same numbers the scalars produced - with
the source moved to governed, effective-dated data.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.config import settings
from app.contracts.rate_cards import RateCard, RateCardScopeKind
from app.services.rate_card_store import get_rate_card_repository

DEFAULT_LIVE_TEXT_CARD_ID = "default-live-text"

# Fields the seeder owns; provenance timestamps are managed by idempotency.
_SEED_MANAGED_EXCLUDES = {"created_at", "last_updated_at"}


def ensure_rate_cards_seeded() -> None:
    """Idempotently migrate the legacy cost scalars into the default card."""

    if (
        settings.live_text_input_cost_per_1k_tokens is None
        or settings.live_text_output_cost_per_1k_tokens is None
    ):
        return
    repository = get_rate_card_repository()
    now = _utc_now_iso()
    desired = RateCard(
        card_id=DEFAULT_LIVE_TEXT_CARD_ID,
        scope_kind=RateCardScopeKind.DEFAULT_LIVE_TEXT,
        currency="USD",
        input_cost_per_1k_tokens=settings.live_text_input_cost_per_1k_tokens,
        output_cost_per_1k_tokens=settings.live_text_output_cost_per_1k_tokens,
        effective_from_utc=None,
        effective_to_utc=None,
        created_at=now,
        last_updated_at=now,
    )
    existing = repository.get_card(DEFAULT_LIVE_TEXT_CARD_ID)
    if existing is None:
        repository.upsert_card(desired)
        return
    # Effective windows on the existing card are governed operator data; the
    # seed owns the prices, never the bounds (the #175 resurrection lesson).
    candidate = desired.model_copy(
        update={
            "created_at": existing.created_at,
            "effective_from_utc": existing.effective_from_utc,
            "effective_to_utc": existing.effective_to_utc,
        }
    )
    if candidate.model_dump(exclude=_SEED_MANAGED_EXCLUDES) == existing.model_dump(
        exclude=_SEED_MANAGED_EXCLUDES
    ):
        return
    repository.upsert_card(candidate)


def resolve_effective_live_text_card(*, at_utc: str | None = None) -> RateCard | None:
    ensure_rate_cards_seeded()
    instant = _parse_utc(at_utc) if at_utc is not None else datetime.now(UTC)
    for card in get_rate_card_repository().list_cards():
        if card.scope_kind is not RateCardScopeKind.DEFAULT_LIVE_TEXT:
            continue
        if card.effective_from_utc is not None and _parse_utc(card.effective_from_utc) > instant:
            continue
        if card.effective_to_utc is not None and instant >= _parse_utc(card.effective_to_utc):
            continue
        return card
    return None


def estimate_live_text_cost_usd(
    *, input_tokens: int | None, output_tokens: int | None
) -> float | None:
    if input_tokens is None or output_tokens is None:
        return None
    card = resolve_effective_live_text_card()
    if card is None:
        return None
    return round(
        (input_tokens / 1000.0) * card.input_cost_per_1k_tokens
        + (output_tokens / 1000.0) * card.output_cost_per_1k_tokens,
        8,
    )


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
