"""add rate-card cost identity to audit records

Revision ID: 0054_add_audit_cost_identity
Revises: 0053_add_rate_card_scope_target
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0054_add_audit_cost_identity"
down_revision = "0053_add_rate_card_scope_target"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_records", sa.Column("estimated_cost_usd", sa.Float(), nullable=True))
    op.add_column("audit_records", sa.Column("rate_card_ref", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_records", "rate_card_ref")
    op.drop_column("audit_records", "estimated_cost_usd")
