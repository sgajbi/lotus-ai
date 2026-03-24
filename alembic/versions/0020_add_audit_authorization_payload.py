"""add audit authorization payload

Revision ID: 0020_add_audit_authorization_payload
Revises: 0019_add_caller_policy_tables
Create Date: 2026-03-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0020_add_audit_authorization_payload"
down_revision = "0019_add_caller_policy_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_records", sa.Column("authorization_payload", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_records", "authorization_payload")
