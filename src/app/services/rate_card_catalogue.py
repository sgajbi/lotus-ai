from __future__ import annotations

from app.config import settings
from app.contracts.rate_cards import RateCardCatalogueResponse
from app.services.provider_usage_accounting import ensure_rate_cards_seeded
from app.services.rate_card_store import get_rate_card_repository


def build_rate_card_catalogue() -> RateCardCatalogueResponse:
    ensure_rate_cards_seeded()
    return RateCardCatalogueResponse(
        service=settings.service_name,
        version=settings.service_version,
        store_mode=settings.rate_card_store_mode,
        cards=get_rate_card_repository().list_cards(),
    )
