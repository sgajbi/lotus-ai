"""add model catalogue lifecycle events

Revision ID: 0046_add_model_lifecycle_events
Revises: 0045_add_kill_switch_activations
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0046_add_model_lifecycle_events"
down_revision = "0045_add_kill_switch_activations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_catalogue_lifecycle_events",
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("entry_id", sa.String(length=256), nullable=False),
        sa.Column("from_state", sa.String(length=32), nullable=False),
        sa.Column("to_state", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("approved_by", sa.String(length=128), nullable=False),
        sa.Column("approval_evidence_ref", sa.String(length=256), nullable=True),
        sa.Column("recorded_at", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_model_catalogue_lifecycle_events_entry_id",
        "model_catalogue_lifecycle_events",
        ["entry_id"],
        unique=False,
    )
    op.create_index(
        "ix_model_catalogue_lifecycle_events_recorded_at",
        "model_catalogue_lifecycle_events",
        ["recorded_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_model_catalogue_lifecycle_events_recorded_at",
        table_name="model_catalogue_lifecycle_events",
    )
    op.drop_index(
        "ix_model_catalogue_lifecycle_events_entry_id",
        table_name="model_catalogue_lifecycle_events",
    )
    op.drop_table("model_catalogue_lifecycle_events")
