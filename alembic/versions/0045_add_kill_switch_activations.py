"""add kill switch activations

Revision ID: 0045_add_kill_switch_activations
Revises: 0044_add_audit_routing_decision
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0045_add_kill_switch_activations"
down_revision = "0044_add_audit_routing_decision"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kill_switch_activations",
        sa.Column("switch_id", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("target", sa.String(length=256), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("approved_by", sa.String(length=128), nullable=False),
        sa.Column("activated_at", sa.String(length=64), nullable=False),
        sa.Column("expires_at_utc", sa.String(length=64), nullable=True),
        sa.Column("cleared_at", sa.String(length=64), nullable=True),
        sa.Column("cleared_by", sa.String(length=128), nullable=True),
        sa.Column("clear_reason", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("switch_id"),
    )
    op.create_index(
        "ix_kill_switch_activations_scope", "kill_switch_activations", ["scope"], unique=False
    )
    op.create_index(
        "ix_kill_switch_activations_target", "kill_switch_activations", ["target"], unique=False
    )
    op.create_index(
        "ix_kill_switch_activations_activated_at",
        "kill_switch_activations",
        ["activated_at"],
        unique=False,
    )
    op.create_index(
        "ix_kill_switch_activations_cleared_at",
        "kill_switch_activations",
        ["cleared_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_kill_switch_activations_cleared_at", table_name="kill_switch_activations")
    op.drop_index("ix_kill_switch_activations_activated_at", table_name="kill_switch_activations")
    op.drop_index("ix_kill_switch_activations_target", table_name="kill_switch_activations")
    op.drop_index("ix_kill_switch_activations_scope", table_name="kill_switch_activations")
    op.drop_table("kill_switch_activations")
