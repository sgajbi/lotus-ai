"""add audit caller identity fields

Revision ID: 0007_add_audit_caller_identity_fields
Revises: 0006_add_audit_execution_context_fields
Create Date: 2026-03-22 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_add_audit_caller_identity_fields"
down_revision = "0006_add_audit_execution_context_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audit_records",
        sa.Column("requested_by", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "audit_records",
        sa.Column("tenant_id", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("audit_records", "tenant_id")
    op.drop_column("audit_records", "requested_by")
