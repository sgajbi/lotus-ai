from __future__ import annotations

from app.contracts.rate_cards import RateCard


class InMemoryRateCardRepository:
    def __init__(self) -> None:
        self._cards: dict[str, RateCard] = {}

    def list_cards(self) -> list[RateCard]:
        return [self._cards[card_id].model_copy(deep=True) for card_id in sorted(self._cards)]

    def get_card(self, card_id: str) -> RateCard | None:
        card = self._cards.get(card_id)
        return card.model_copy(deep=True) if card is not None else None

    def upsert_card(self, card: RateCard) -> None:
        self._cards[card.card_id] = card.model_copy(deep=True)
