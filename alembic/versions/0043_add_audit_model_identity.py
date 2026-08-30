"""add first-class model identity columns to audit records

Revision ID: 0043_add_audit_model_identity
Revises: 0042_add_model_catalogue
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0043_add_audit_model_identity"
down_revision = "0042_add_model_catalogue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_records", sa.Column("provider_id", sa.String(length=128), nullable=True))
    op.add_column("audit_records", sa.Column("adapter_kind", sa.String(length=64), nullable=True))
    op.add_column("audit_records", sa.Column("model_id", sa.String(length=128), nullable=True))
    op.add_column("audit_records", sa.Column("model_version", sa.String(length=128), nullable=True))
    op.add_column(
        "audit_records",
        sa.Column("model_catalogue_entry_id", sa.String(length=256), nullable=True),
    )
    op.add_column("audit_records", sa.Column("model_revision_pinned", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_records", "model_revision_pinned")
    op.drop_column("audit_records", "model_catalogue_entry_id")
    op.drop_column("audit_records", "model_version")
    op.drop_column("audit_records", "model_id")
    op.drop_column("audit_records", "adapter_kind")
    op.drop_column("audit_records", "provider_id")
