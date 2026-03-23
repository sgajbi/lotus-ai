"""add audit execution outcome payload

Revision ID: 0015_add_audit_execution_outcome_payload
Revises: 0014_add_evaluation_runtime_state_tables
Create Date: 2026-03-23 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0015_add_audit_execution_outcome_payload"
down_revision = "0014_add_evaluation_runtime_state_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audit_records",
        sa.Column(
            "execution_status",
            sa.String(length=32),
            nullable=False,
            server_default="COMPLETED",
        ),
    )
    op.add_column(
        "audit_records",
        sa.Column("safety_outcome_payload", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("audit_records", "safety_outcome_payload")
    op.drop_column("audit_records", "execution_status")
