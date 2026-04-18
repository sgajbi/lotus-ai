"""add workflow pack run ledger tables

Revision ID: 0028_add_workflow_pack_run_ledger_tables
Revises: 0027_allow_lotus_gateway_live_provider
Create Date: 2026-04-18 15:15:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0028_add_workflow_pack_run_ledger_tables"
down_revision = "0027_allow_lotus_gateway_live_provider"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_pack_runs",
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("pack_id", sa.String(length=128), nullable=False),
        sa.Column("pack_family", sa.String(length=128), nullable=False),
        sa.Column("pack_version", sa.String(length=64), nullable=False),
        sa.Column("registration_ref", sa.String(length=256), nullable=False),
        sa.Column("task_id", sa.String(length=128), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("caller_app", sa.String(length=128), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=True),
        sa.Column("workflow_surface", sa.String(length=128), nullable=True),
        sa.Column("workflow_authority_owner", sa.String(length=128), nullable=False),
        sa.Column("runtime_state", sa.String(length=32), nullable=False),
        sa.Column("review_state", sa.String(length=32), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("provider_mode", sa.String(length=64), nullable=False),
        sa.Column("stubbed", sa.Boolean(), nullable=False),
        sa.Column("output_preview", sa.Text(), nullable=False),
        sa.Column(
            "structured_output_keys",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "evidence_descriptors",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("artifact_refs", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("supersedes_run_id", sa.String(length=128), nullable=True),
        sa.Column("superseded_by_run_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("completed_at", sa.String(length=64), nullable=True),
        sa.Column("last_updated_at", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index(
        "ix_workflow_pack_runs_pack_id", "workflow_pack_runs", ["pack_id"], unique=False
    )
    op.create_index(
        "ix_workflow_pack_runs_pack_family",
        "workflow_pack_runs",
        ["pack_family"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_runs_task_id", "workflow_pack_runs", ["task_id"], unique=False
    )
    op.create_index(
        "ix_workflow_pack_runs_request_id",
        "workflow_pack_runs",
        ["request_id"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_runs_tenant_id",
        "workflow_pack_runs",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_runs_runtime_state",
        "workflow_pack_runs",
        ["runtime_state"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_runs_review_state",
        "workflow_pack_runs",
        ["review_state"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_runs_created_at",
        "workflow_pack_runs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_runs_last_updated_at",
        "workflow_pack_runs",
        ["last_updated_at"],
        unique=False,
    )

    op.create_table(
        "workflow_pack_run_events",
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("runtime_state", sa.String(length=32), nullable=False),
        sa.Column("review_state", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_pack_runs.run_id"]),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_workflow_pack_run_events_run_id",
        "workflow_pack_run_events",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_run_events_event_type",
        "workflow_pack_run_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_run_events_recorded_at",
        "workflow_pack_run_events",
        ["recorded_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_pack_run_events_recorded_at", table_name="workflow_pack_run_events")
    op.drop_index("ix_workflow_pack_run_events_event_type", table_name="workflow_pack_run_events")
    op.drop_index("ix_workflow_pack_run_events_run_id", table_name="workflow_pack_run_events")
    op.drop_table("workflow_pack_run_events")

    op.drop_index("ix_workflow_pack_runs_last_updated_at", table_name="workflow_pack_runs")
    op.drop_index("ix_workflow_pack_runs_created_at", table_name="workflow_pack_runs")
    op.drop_index("ix_workflow_pack_runs_review_state", table_name="workflow_pack_runs")
    op.drop_index("ix_workflow_pack_runs_runtime_state", table_name="workflow_pack_runs")
    op.drop_index("ix_workflow_pack_runs_tenant_id", table_name="workflow_pack_runs")
    op.drop_index("ix_workflow_pack_runs_request_id", table_name="workflow_pack_runs")
    op.drop_index("ix_workflow_pack_runs_task_id", table_name="workflow_pack_runs")
    op.drop_index("ix_workflow_pack_runs_pack_family", table_name="workflow_pack_runs")
    op.drop_index("ix_workflow_pack_runs_pack_id", table_name="workflow_pack_runs")
    op.drop_table("workflow_pack_runs")
