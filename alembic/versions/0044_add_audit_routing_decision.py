"""add routing decision payload to audit records

Revision ID: 0044_add_audit_routing_decision
Revises: 0043_add_audit_model_identity
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0044_add_audit_routing_decision"
down_revision = "0043_add_audit_model_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_records", sa.Column("routing_decision_payload", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_records", "routing_decision_payload")
