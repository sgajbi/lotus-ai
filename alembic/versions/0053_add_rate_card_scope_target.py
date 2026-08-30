"""add scope target to rate cards for model-revision pricing

Revision ID: 0053_add_rate_card_scope_target
Revises: 0052_add_kill_switch_expiry_marker
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0053_add_rate_card_scope_target"
down_revision = "0052_add_kill_switch_expiry_marker"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rate_cards",
        sa.Column("scope_target", sa.String(length=256), nullable=True),
    )
    op.create_index("ix_rate_cards_scope_target", "rate_cards", ["scope_target"])


def downgrade() -> None:
    op.drop_index("ix_rate_cards_scope_target", table_name="rate_cards")
    op.drop_column("rate_cards", "scope_target")
