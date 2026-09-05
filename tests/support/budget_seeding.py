"""Seed settled provider spend through the one remaining debit lifecycle.

``record_attempt_spend`` -- the uncoupled single-shot debit writer -- was
removed in the follow-up to #333: reserve->settle is the complete lifecycle,
and a second writer that skipped admission was exactly the kind of path the
identity audit closes. Tests that need historical spend on the books seed it
here, through the real pair, with enforcement suspended for the duration so
history can exceed the configured limits (as real history can).
"""

from __future__ import annotations

from app.config import settings
from app.services.provider_budget_policy import (
    reserve_attempt_spend,
    settle_attempt_spend,
)
from app.services.provider_usage_accounting import AttemptDebit


def seed_settled_attempt_spend(
    amount_usd: float,
    *,
    execution_id: str,
    attempt_index: int = 0,
    input_tokens: int = 100,
    output_tokens: int = 200,
) -> bool:
    """Reserve and settle one ACTUAL_USAGE debit; True when newly settled.

    A repeat of the same attempt identity converges: the reservation reports
    DUPLICATE and the settlement is a no-op, so the return value preserves
    the old recorder's recorded/duplicate contract.
    """

    debit = AttemptDebit(
        amount_usd=amount_usd,
        basis="ACTUAL_USAGE",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        rate_card_ref="default-live-text",
    )
    previous = settings.live_text_budget_enforced
    settings.live_text_budget_enforced = False
    try:
        reserve_attempt_spend(
            execution_id=execution_id,
            candidate_entry_id="text.openai:gpt-5.4",
            provider_id="text.openai",
            model_revision="gpt-5.4",
            attempt_index=attempt_index,
            reservation=debit,
            candidate_id_v2=None,
        )
        return settle_attempt_spend(
            execution_id=execution_id,
            candidate_entry_id="text.openai:gpt-5.4",
            attempt_index=attempt_index,
            debit=debit,
            candidate_id_v2=None,
        )
    finally:
        settings.live_text_budget_enforced = previous
