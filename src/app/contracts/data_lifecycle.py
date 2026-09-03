"""Data-lifecycle evidence and legal-hold contracts (issue #158, S2a)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class DataLifecycleAction(str, Enum):
    EXPIRY = "EXPIRY"


class DataLifecycleEventRecord(BaseModel):
    """One append-only deletion-evidence row: deletion never removes the
    evidence of deletion, and content is referenced only by digest."""

    event_id: str = Field(min_length=1, max_length=64)
    family_id: str = Field(min_length=1, max_length=128)
    action: DataLifecycleAction
    key_scope: str | None = Field(
        default=None,
        max_length=256,
        description="Key scope the action applied to, when narrower than the family.",
    )
    row_count: int = Field(ge=1)
    policy_version: str = Field(min_length=1, max_length=16)
    actor: str = Field(min_length=1, max_length=256)
    deleted_ids_digest: str = Field(
        min_length=64,
        max_length=64,
        description="sha256 over the sorted deleted primary keys - evidence without content.",
    )
    recorded_at: str = Field(min_length=1, max_length=64)


class DataLegalHoldRecord(BaseModel):
    """An active hold while released_at is null: legal hold overrides expiry,
    and (from S3) erasure - both recorded."""

    hold_id: str = Field(min_length=1, max_length=64)
    family_id: str = Field(min_length=1, max_length=128)
    key_type: str = Field(min_length=1, max_length=32)
    key_value: str = Field(min_length=1, max_length=256)
    reason: str = Field(min_length=1)
    placed_by: str = Field(min_length=1, max_length=256)
    placed_at: str = Field(min_length=1, max_length=64)
    released_at: str | None = Field(default=None, max_length=64)
