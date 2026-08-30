"""Usage cost accounting, sourced from the rate-card catalogue (issue #178).

The two legacy cost scalars are seed inputs only: the seed migrates them into
the DEFAULT_LIVE_TEXT rate card, and estimation resolves the effective card
for the routed identity at the execution instant (S2):

- resolution precedence: a MODEL_REVISION card matching the routed revision
  beats the DEFAULT_LIVE_TEXT card; among candidates the latest
  effective_from wins (a new effective row changes costs only for
  executions after its instant), ties broken by card_id for determinism.
- every estimate carries the rate_card_ref of the card that priced it; no
  applicable card is an explicit cost-unknown posture (estimate and ref are
  both None) and never blocks execution - economics observe, policy decides.
- embedding executions price through the EMBEDDING_DEFAULT scope the same
  way; no seed exists for it, so pricing starts when an operator-supplied
  card does.

Writes go through save_rate_card, which refuses overlapping effective
ranges for the same scope key - the write-side invariant every producer
(seed, eval fixtures, tests, future operator API) shares.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.rate_cards import RateCard, RateCardScopeKind
from app.services.rate_card_store import get_rate_card_repository

DEFAULT_LIVE_TEXT_CARD_ID = "default-live-text"

# Fields the seeder owns; provenance timestamps are managed by idempotency.
_SEED_MANAGED_EXCLUDES = {"created_at", "last_updated_at"}


@dataclass(frozen=True)
class UsageCostEstimate:
    estimated_cost_usd: float | None
    rate_card_ref: str | None

    @property
    def cost_posture(self) -> str:
        return "ESTIMATED" if self.rate_card_ref is not None else "UNKNOWN"


UNKNOWN_COST = UsageCostEstimate(estimated_cost_usd=None, rate_card_ref=None)


def save_rate_card(card: RateCard) -> None:
    """Persist one rate card, refusing overlapping effective ranges.

    Two cards for the same scope key may not have intersecting effective
    windows (an open bound intersects everything on its side); replacing a
    card under its own id is always allowed.
    """

    repository = get_rate_card_repository()
    for existing in repository.list_cards():
        if existing.card_id == card.card_id:
            continue
        if existing.scope_kind is not card.scope_kind or existing.scope_target != card.scope_target:
            continue
        if _windows_overlap(card, existing):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Rate card `{card.card_id}` overlaps the effective range of "
                    f"`{existing.card_id}` for scope {card.scope_kind.value}"
                    f"{f' target {card.scope_target}' if card.scope_target else ''}; "
                    "close the existing window before adding a new one."
                ),
            )
    repository.upsert_card(card)


def _windows_overlap(first: RateCard, second: RateCard) -> bool:
    first_from = _parse_utc(first.effective_from_utc) if first.effective_from_utc else None
    first_to = _parse_utc(first.effective_to_utc) if first.effective_to_utc else None
    second_from = _parse_utc(second.effective_from_utc) if second.effective_from_utc else None
    second_to = _parse_utc(second.effective_to_utc) if second.effective_to_utc else None
    if first_to is not None and second_from is not None and first_to <= second_from:
        return False
    if second_to is not None and first_from is not None and second_to <= first_from:
        return False
    return True


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
        save_rate_card(desired)
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


def _effective_candidates(
    *,
    scope_kind: RateCardScopeKind,
    scope_target: str | None,
    instant: datetime,
) -> list[RateCard]:
    candidates = []
    for card in get_rate_card_repository().list_cards():
        if card.scope_kind is not scope_kind or card.scope_target != scope_target:
            continue
        if card.effective_from_utc is not None and _parse_utc(card.effective_from_utc) > instant:
            continue
        if card.effective_to_utc is not None and instant >= _parse_utc(card.effective_to_utc):
            continue
        candidates.append(card)
    # Latest effective_from wins (None sorts earliest); card_id breaks ties
    # deterministically.
    return sorted(
        candidates,
        key=lambda card: (
            _parse_utc(card.effective_from_utc)
            if card.effective_from_utc
            else datetime.min.replace(tzinfo=UTC),
            card.card_id,
        ),
        reverse=True,
    )


def resolve_effective_live_text_card(
    *,
    model_revision: str | None = None,
    at_utc: str | None = None,
) -> RateCard | None:
    ensure_rate_cards_seeded()
    instant = _parse_utc(at_utc) if at_utc is not None else datetime.now(UTC)
    if model_revision is not None:
        scoped = _effective_candidates(
            scope_kind=RateCardScopeKind.MODEL_REVISION,
            scope_target=model_revision,
            instant=instant,
        )
        if scoped:
            return scoped[0]
    defaults = _effective_candidates(
        scope_kind=RateCardScopeKind.DEFAULT_LIVE_TEXT, scope_target=None, instant=instant
    )
    return defaults[0] if defaults else None


def estimate_live_text_cost(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    model_revision: str | None = None,
    at_utc: str | None = None,
) -> UsageCostEstimate:
    if input_tokens is None or output_tokens is None:
        return UNKNOWN_COST
    card = resolve_effective_live_text_card(model_revision=model_revision, at_utc=at_utc)
    if card is None:
        return UNKNOWN_COST
    return UsageCostEstimate(
        estimated_cost_usd=_price(card, input_tokens=input_tokens, output_tokens=output_tokens),
        rate_card_ref=card.card_id,
    )


def resolve_effective_embedding_card(*, at_utc: str | None = None) -> RateCard | None:
    instant = _parse_utc(at_utc) if at_utc is not None else datetime.now(UTC)
    candidates = _effective_candidates(
        scope_kind=RateCardScopeKind.EMBEDDING_DEFAULT, scope_target=None, instant=instant
    )
    return candidates[0] if candidates else None


def estimate_embedding_cost(
    *,
    input_tokens: int | None,
    at_utc: str | None = None,
) -> UsageCostEstimate:
    if input_tokens is None:
        return UNKNOWN_COST
    card = resolve_effective_embedding_card(at_utc=at_utc)
    if card is None:
        return UNKNOWN_COST
    return UsageCostEstimate(
        estimated_cost_usd=_price(card, input_tokens=input_tokens, output_tokens=0),
        rate_card_ref=card.card_id,
    )


def _price(card: RateCard, *, input_tokens: int, output_tokens: int) -> float:
    return round(
        (input_tokens / 1000.0) * card.input_cost_per_1k_tokens
        + (output_tokens / 1000.0) * card.output_cost_per_1k_tokens,
        8,
    )


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
