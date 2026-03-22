from __future__ import annotations

from app.config import settings


def estimate_live_text_cost_usd(
    *, input_tokens: int | None, output_tokens: int | None
) -> float | None:
    if input_tokens is None or output_tokens is None:
        return None
    if settings.live_text_input_cost_per_1k_tokens is None:
        return None
    if settings.live_text_output_cost_per_1k_tokens is None:
        return None
    return round(
        (input_tokens / 1000.0) * settings.live_text_input_cost_per_1k_tokens
        + (output_tokens / 1000.0) * settings.live_text_output_cost_per_1k_tokens,
        8,
    )
