from __future__ import annotations

from typing import Protocol

from app.contracts.rate_cards import RateCard


class RateCardRepository(Protocol):
    def list_cards(self) -> list[RateCard]: ...

    def get_card(self, card_id: str) -> RateCard | None: ...

    def upsert_card(self, card: RateCard) -> None: ...
