"""add durable expiry-event marker to kill-switch activations

Revision ID: 0052_add_kill_switch_expiry_marker
Revises: 0051_add_kill_switch_semantics
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0052_add_kill_switch_expiry_marker"
down_revision = "0051_add_kill_switch_semantics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "kill_switch_activations",
        sa.Column("expiry_recorded_at", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("kill_switch_activations", "expiry_recorded_at")
