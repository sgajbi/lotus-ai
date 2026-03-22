from app.config import settings
from app.services.provider_usage_accounting import estimate_live_text_cost_usd


def test_estimate_live_text_cost_usd_returns_none_without_rate_card() -> None:
    assert estimate_live_text_cost_usd(input_tokens=100, output_tokens=50) is None


def test_estimate_live_text_cost_usd_uses_configured_rate_card() -> None:
    settings.live_text_input_cost_per_1k_tokens = 0.01
    settings.live_text_output_cost_per_1k_tokens = 0.03

    assert estimate_live_text_cost_usd(input_tokens=500, output_tokens=250) == 0.0125


def test_estimate_live_text_cost_usd_returns_none_for_missing_token_counts() -> None:
    settings.live_text_input_cost_per_1k_tokens = 0.01
    settings.live_text_output_cost_per_1k_tokens = 0.03

    assert estimate_live_text_cost_usd(input_tokens=None, output_tokens=250) is None
    assert estimate_live_text_cost_usd(input_tokens=500, output_tokens=None) is None


def test_estimate_live_text_cost_usd_returns_none_for_missing_output_rate() -> None:
    settings.live_text_input_cost_per_1k_tokens = 0.01
    settings.live_text_output_cost_per_1k_tokens = None

    assert estimate_live_text_cost_usd(input_tokens=500, output_tokens=250) is None
