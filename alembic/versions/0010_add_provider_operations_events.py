"""add provider operations events

Revision ID: 0010_add_provider_operations_events
Revises: 0009_add_provider_operations_state_tables
Create Date: 2026-03-23 00:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010_add_provider_operations_events"
down_revision = "0009_add_provider_operations_state_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_operations_events",
        sa.Column("event_id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=True),
        sa.Column("scope_key", sa.String(length=256), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.String(length=256), nullable=False),
        sa.Column("approved_by", sa.String(length=256), nullable=False),
        sa.Column("affected_record_count", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.String(length=64), nullable=False),
    )
    op.create_index(
        "ix_provider_operations_events_action_type",
        "provider_operations_events",
        ["action_type"],
    )
    op.create_index(
        "ix_provider_operations_events_recorded_at",
        "provider_operations_events",
        ["recorded_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_provider_operations_events_recorded_at", table_name="provider_operations_events"
    )
    op.drop_index(
        "ix_provider_operations_events_action_type", table_name="provider_operations_events"
    )
    op.drop_table("provider_operations_events")
