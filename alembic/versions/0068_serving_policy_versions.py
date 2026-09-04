"""serving policy versions

Revision ID: 0068_serving_policy_versions
Revises: 0067_tenant_attribution
Create Date: 2026-09-04

Issue #295, S2: the ordered serving identities become a stored, versioned
policy artifact. Versions are append-only evidence of who may serve and who
changed that; the highest version is operative.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0068_serving_policy_versions"
down_revision = "0067_tenant_attribution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "serving_policy_versions",
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("ordered_entry_ids", sa.JSON(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("changed_entry_id", sa.String(length=256), nullable=False),
        sa.Column("requested_by_key_id", sa.String(length=128), nullable=False),
        sa.Column("approver_key_id", sa.String(length=128), nullable=True),
        sa.Column("governed_action_id", sa.String(length=128), nullable=True),
        sa.Column("recorded_at", sa.String(length=64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("serving_policy_versions")
