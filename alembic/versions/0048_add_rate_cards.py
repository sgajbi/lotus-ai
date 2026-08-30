"""add rate cards

Revision ID: 0048_add_rate_cards
Revises: 0047_add_model_revision_drift
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0048_add_rate_cards"
down_revision = "0047_add_model_revision_drift"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rate_cards",
        sa.Column("card_id", sa.String(length=128), nullable=False),
        sa.Column("scope_kind", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("input_cost_per_1k_tokens", sa.Float(), nullable=False),
        sa.Column("output_cost_per_1k_tokens", sa.Float(), nullable=False),
        sa.Column("effective_from_utc", sa.String(length=64), nullable=True),
        sa.Column("effective_to_utc", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("last_updated_at", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("card_id"),
    )
    op.create_index("ix_rate_cards_scope_kind", "rate_cards", ["scope_kind"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_rate_cards_scope_kind", table_name="rate_cards")
    op.drop_table("rate_cards")
