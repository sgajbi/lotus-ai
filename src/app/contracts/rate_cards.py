"""Versioned provider rate cards (issue #178, slice 1).

The pricing catalogue replaces the two global cost scalars as the source of
cost truth. Slice 1 carries exactly what has a producer today: the default
live-text card the seed migrates from those scalars, with optional effective
dating. Per-model and per-SKU scope kinds arrive with the operator write API
that produces them; cached/batch/embedding prices arrive with their sources.

Prices are floats in this slice for exact cutover parity with the existing
accounting surface; decimalising the money chain is tracked with the
monetary-float guard work (#165), not smuggled in here.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class RateCardScopeKind(str, Enum):
    DEFAULT_LIVE_TEXT = "DEFAULT_LIVE_TEXT"
    MODEL_REVISION = "MODEL_REVISION"
    EMBEDDING_DEFAULT = "EMBEDDING_DEFAULT"


TARGETLESS_RATE_CARD_SCOPES = frozenset(
    {RateCardScopeKind.DEFAULT_LIVE_TEXT, RateCardScopeKind.EMBEDDING_DEFAULT}
)


class RateCard(BaseModel):
    card_id: str = Field(min_length=1, description="Rate-card identity.")
    scope_kind: RateCardScopeKind = Field(
        description="What executions this card prices; DEFAULT_LIVE_TEXT prices every live "
        "text execution (exactly as the legacy scalars did), MODEL_REVISION prices one "
        "routed model revision and beats the default, EMBEDDING_DEFAULT prices embedding "
        "executions.",
    )
    scope_target: str | None = Field(
        default=None,
        description="Scope key (the model revision for MODEL_REVISION); null for the "
        "targetless default scopes.",
    )
    currency: str = Field(description="ISO currency of the prices.")
    input_cost_per_1k_tokens: float = Field(ge=0, description="Price per 1000 input tokens.")
    output_cost_per_1k_tokens: float = Field(ge=0, description="Price per 1000 output tokens.")
    effective_from_utc: str | None = Field(
        default=None,
        description="Effective start (UTC); null means effective since always.",
    )
    effective_to_utc: str | None = Field(
        default=None,
        description="Effective end (UTC), exclusive; null means no expiry.",
    )
    created_at: str = Field(description="Instant this card was first stored (UTC).")

    @model_validator(mode="after")
    def _validate_scope_target(self) -> "RateCard":
        if self.scope_kind in TARGETLESS_RATE_CARD_SCOPES:
            if self.scope_target is not None:
                raise ValueError(f"Scope {self.scope_kind.value} is targetless.")
        elif not self.scope_target:
            raise ValueError(f"Scope {self.scope_kind.value} requires a scope_target.")
        return self

    last_updated_at: str = Field(description="Instant this card last changed (UTC).")


class RateCardCatalogueResponse(BaseModel):
    service: str = Field(description="Service name emitting the rate-card catalogue.")
    version: str = Field(description="Current lotus-ai service version.")
    store_mode: str = Field(description="Where rate-card truth lives: memory or sqlalchemy.")
    cards: list[RateCard] = Field(description="Every stored rate card, ordered by card id.")
