"""add audit execution context fields

Revision ID: 0006_add_audit_execution_context_fields
Revises: 0005_add_audit_safety_metadata
Create Date: 2026-03-22 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_add_audit_execution_context_fields"
down_revision = "0005_add_audit_safety_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audit_records",
        sa.Column("category", sa.String(length=64), nullable=False, server_default="explain"),
    )
    op.add_column(
        "audit_records",
        sa.Column(
            "output_label",
            sa.String(length=64),
            nullable=False,
            server_default="EXPLANATION_ONLY",
        ),
    )
    op.add_column(
        "audit_records",
        sa.Column(
            "evidence",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("audit_records", "evidence")
    op.drop_column("audit_records", "output_label")
    op.drop_column("audit_records", "category")
