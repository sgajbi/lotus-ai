"""add async control events

Revision ID: 0013_add_async_control_events
Revises: 0012_add_async_job_target_id
Create Date: 2026-03-23 18:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0013_add_async_control_events"
down_revision = "0012_add_async_job_target_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "async_control_events",
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("requested_by", sa.String(length=256), nullable=False),
        sa.Column("approved_by", sa.String(length=256), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("prior_status", sa.String(length=64), nullable=False),
        sa.Column("resulting_status", sa.String(length=64), nullable=False),
        sa.Column("affected_attempt_id", sa.String(length=128), nullable=True),
        sa.Column("recorded_at", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["async_jobs.job_id"]),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        op.f("ix_async_control_events_action_type"),
        "async_control_events",
        ["action_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_async_control_events_job_id"),
        "async_control_events",
        ["job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_async_control_events_recorded_at"),
        "async_control_events",
        ["recorded_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_async_control_events_recorded_at"), table_name="async_control_events")
    op.drop_index(op.f("ix_async_control_events_job_id"), table_name="async_control_events")
    op.drop_index(op.f("ix_async_control_events_action_type"), table_name="async_control_events")
    op.drop_table("async_control_events")
