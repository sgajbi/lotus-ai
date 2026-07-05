"""add workflow pack run recovery lineage

Revision ID: 0035_add_workflow_pack_run_recovery_lineage
Revises: 0034_seed_lotus_idea_caller_policy
Create Date: 2026-07-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0035_add_workflow_pack_run_recovery_lineage"
down_revision = "0034_seed_lotus_idea_caller_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workflow_pack_runs",
        sa.Column("recovery_action_type", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "workflow_pack_runs",
        sa.Column("source_queue_item_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "workflow_pack_runs",
        sa.Column("recovery_decision_event_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "workflow_pack_runs",
        sa.Column("recovery_attempt_number", sa.Integer(), nullable=True),
    )
    op.add_column(
        "workflow_pack_runs",
        sa.Column("source_workflow_pack_run_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "workflow_pack_runs",
        sa.Column("recovery_requested_by", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "workflow_pack_runs",
        sa.Column("recovery_evidence_ref", sa.String(length=256), nullable=True),
    )
    for column_name in [
        "recovery_action_type",
        "source_queue_item_id",
        "recovery_decision_event_id",
        "source_workflow_pack_run_id",
    ]:
        op.create_index(
            f"ix_workflow_pack_runs_{column_name}",
            "workflow_pack_runs",
            [column_name],
            unique=False,
        )


def downgrade() -> None:
    for column_name in [
        "source_workflow_pack_run_id",
        "recovery_decision_event_id",
        "source_queue_item_id",
        "recovery_action_type",
    ]:
        op.drop_index(f"ix_workflow_pack_runs_{column_name}", table_name="workflow_pack_runs")
    for column_name in [
        "recovery_evidence_ref",
        "recovery_requested_by",
        "source_workflow_pack_run_id",
        "recovery_attempt_number",
        "recovery_decision_event_id",
        "source_queue_item_id",
        "recovery_action_type",
    ]:
        op.drop_column("workflow_pack_runs", column_name)
