"""add workflow pack task flow tables

Revision ID: 0031_add_workflow_pack_task_flow_tables
Revises: 0030_add_workflow_pack_control_event_authorization_payload
Create Date: 2026-04-21 10:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0031_add_workflow_pack_task_flow_tables"
down_revision = "0030_add_workflow_pack_control_event_authorization_payload"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_pack_task_flows",
        sa.Column("task_flow_id", sa.String(length=128), nullable=False),
        sa.Column("workflow_pack_id", sa.String(length=128), nullable=False),
        sa.Column("workflow_pack_version", sa.String(length=64), nullable=False),
        sa.Column("caller", sa.String(length=128), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=True),
        sa.Column("workflow_surface", sa.String(length=128), nullable=True),
        sa.Column("workflow_authority_owner", sa.String(length=128), nullable=False),
        sa.Column("flow_status", sa.String(length=32), nullable=False),
        sa.Column("supportability_status", sa.String(length=32), nullable=False),
        sa.Column("current_step_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.String(length=64), nullable=True),
        sa.Column("descriptor_payload", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("task_flow_id"),
    )
    op.create_index(
        "ix_workflow_pack_task_flows_workflow_pack_id",
        "workflow_pack_task_flows",
        ["workflow_pack_id"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_task_flows_caller",
        "workflow_pack_task_flows",
        ["caller"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_task_flows_tenant_id",
        "workflow_pack_task_flows",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_task_flows_workflow_surface",
        "workflow_pack_task_flows",
        ["workflow_surface"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_task_flows_flow_status",
        "workflow_pack_task_flows",
        ["flow_status"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_task_flows_supportability_status",
        "workflow_pack_task_flows",
        ["supportability_status"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_task_flows_created_at",
        "workflow_pack_task_flows",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_task_flows_updated_at",
        "workflow_pack_task_flows",
        ["updated_at"],
        unique=False,
    )

    op.create_table(
        "workflow_pack_task_flow_checkpoints",
        sa.Column("checkpoint_id", sa.String(length=128), nullable=False),
        sa.Column("task_flow_id", sa.String(length=128), nullable=False),
        sa.Column("step_id", sa.String(length=128), nullable=False),
        sa.Column("transition", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("recorded_at", sa.String(length=64), nullable=False),
        sa.Column("degraded", sa.Boolean(), nullable=False),
        sa.Column("unsupported", sa.Boolean(), nullable=False),
        sa.Column("descriptor_payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["task_flow_id"], ["workflow_pack_task_flows.task_flow_id"]),
        sa.PrimaryKeyConstraint("checkpoint_id"),
    )
    op.create_index(
        "ix_workflow_pack_task_flow_checkpoints_task_flow_id",
        "workflow_pack_task_flow_checkpoints",
        ["task_flow_id"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_task_flow_checkpoints_step_id",
        "workflow_pack_task_flow_checkpoints",
        ["step_id"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_task_flow_checkpoints_transition",
        "workflow_pack_task_flow_checkpoints",
        ["transition"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_task_flow_checkpoints_recorded_at",
        "workflow_pack_task_flow_checkpoints",
        ["recorded_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_pack_task_flow_checkpoints_recorded_at",
        table_name="workflow_pack_task_flow_checkpoints",
    )
    op.drop_index(
        "ix_workflow_pack_task_flow_checkpoints_transition",
        table_name="workflow_pack_task_flow_checkpoints",
    )
    op.drop_index(
        "ix_workflow_pack_task_flow_checkpoints_step_id",
        table_name="workflow_pack_task_flow_checkpoints",
    )
    op.drop_index(
        "ix_workflow_pack_task_flow_checkpoints_task_flow_id",
        table_name="workflow_pack_task_flow_checkpoints",
    )
    op.drop_table("workflow_pack_task_flow_checkpoints")

    op.drop_index("ix_workflow_pack_task_flows_updated_at", table_name="workflow_pack_task_flows")
    op.drop_index("ix_workflow_pack_task_flows_created_at", table_name="workflow_pack_task_flows")
    op.drop_index(
        "ix_workflow_pack_task_flows_supportability_status",
        table_name="workflow_pack_task_flows",
    )
    op.drop_index(
        "ix_workflow_pack_task_flows_flow_status", table_name="workflow_pack_task_flows"
    )
    op.drop_index(
        "ix_workflow_pack_task_flows_workflow_surface",
        table_name="workflow_pack_task_flows",
    )
    op.drop_index("ix_workflow_pack_task_flows_tenant_id", table_name="workflow_pack_task_flows")
    op.drop_index("ix_workflow_pack_task_flows_caller", table_name="workflow_pack_task_flows")
    op.drop_index(
        "ix_workflow_pack_task_flows_workflow_pack_id",
        table_name="workflow_pack_task_flows",
    )
    op.drop_table("workflow_pack_task_flows")
