"""Cost estimation semantics, sourced from the rate-card catalogue (#178 S1).

The inventory-era cases are preserved one for one: no configuration means no
cost, both rates present price the tokens, missing token counts price nothing,
and a partial rate configuration seeds no card and therefore prices nothing.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.config import settings
from app.services.provider_usage_accounting import estimate_live_text_cost_usd
from app.services.rate_card_store import reset_rate_card_store_cache


@pytest.fixture(autouse=True)
def _fresh_rate_cards(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(settings, "live_text_input_cost_per_1k_tokens", None)
    monkeypatch.setattr(settings, "live_text_output_cost_per_1k_tokens", None)
    reset_rate_card_store_cache()
    yield
    reset_rate_card_store_cache()


def test_estimate_live_text_cost_usd_returns_none_without_rate_card() -> None:
    assert estimate_live_text_cost_usd(input_tokens=100, output_tokens=50) is None


def test_estimate_live_text_cost_usd_uses_the_seeded_rate_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "live_text_input_cost_per_1k_tokens", 0.01)
    monkeypatch.setattr(settings, "live_text_output_cost_per_1k_tokens", 0.03)

    assert estimate_live_text_cost_usd(input_tokens=500, output_tokens=250) == 0.0125


def test_estimate_live_text_cost_usd_returns_none_for_missing_token_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "live_text_input_cost_per_1k_tokens", 0.01)
    monkeypatch.setattr(settings, "live_text_output_cost_per_1k_tokens", 0.03)

    assert estimate_live_text_cost_usd(input_tokens=None, output_tokens=250) is None
    assert estimate_live_text_cost_usd(input_tokens=500, output_tokens=None) is None


def test_estimate_live_text_cost_usd_returns_none_for_partial_rate_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "live_text_input_cost_per_1k_tokens", 0.01)
    monkeypatch.setattr(settings, "live_text_output_cost_per_1k_tokens", None)

    # A partial configuration seeds no card, so nothing is priced.
    assert estimate_live_text_cost_usd(input_tokens=500, output_tokens=250) is None
