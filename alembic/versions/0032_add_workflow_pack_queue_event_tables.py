"""add workflow pack queue event tables

Revision ID: 0032_add_workflow_pack_queue_event_tables
Revises: 0031_add_workflow_pack_task_flow_tables
Create Date: 2026-04-21 14:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0032_add_workflow_pack_queue_event_tables"
down_revision = "0031_add_workflow_pack_task_flow_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_pack_queue_events",
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("queue_item_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=True),
        sa.Column("workflow_pack_id", sa.String(length=128), nullable=False),
        sa.Column("workflow_pack_version", sa.String(length=64), nullable=False),
        sa.Column("lane", sa.String(length=64), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("caller_app", sa.String(length=128), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=True),
        sa.Column("workflow_surface", sa.String(length=128), nullable=True),
        sa.Column("reason_code", sa.String(length=128), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.String(length=64), nullable=False),
        sa.Column("descriptor_payload", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )
    for column_name in [
        "queue_item_id",
        "event_type",
        "policy_id",
        "workflow_pack_id",
        "lane",
        "state",
        "caller_app",
        "tenant_id",
        "workflow_surface",
        "reason_code",
        "recorded_at",
    ]:
        op.create_index(
            f"ix_workflow_pack_queue_events_{column_name}",
            "workflow_pack_queue_events",
            [column_name],
            unique=False,
        )


def downgrade() -> None:
    for column_name in [
        "recorded_at",
        "reason_code",
        "workflow_surface",
        "tenant_id",
        "caller_app",
        "state",
        "lane",
        "workflow_pack_id",
        "policy_id",
        "event_type",
        "queue_item_id",
    ]:
        op.drop_index(
            f"ix_workflow_pack_queue_events_{column_name}",
            table_name="workflow_pack_queue_events",
        )
    op.drop_table("workflow_pack_queue_events")
