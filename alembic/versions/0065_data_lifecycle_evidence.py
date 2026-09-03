"""data lifecycle evidence

Revision ID: 0065_data_lifecycle_evidence
Revises: 0064_scoped_structured_output_evidence
Create Date: 2026-09-03

Issue #158, S2a: the evidence table lands before anything destructive runs.
data_lifecycle_events is append-only deletion evidence (family, count,
policy version, digest of deleted ids - never the content);
data_legal_holds makes legal hold a first-class row the engine must honour
before deleting anything.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0065_data_lifecycle_evidence"
down_revision = "0064_scoped_structured_output_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_lifecycle_events",
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("family_id", sa.String(128), nullable=False, index=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("key_scope", sa.String(256), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("policy_version", sa.String(16), nullable=False),
        sa.Column("actor", sa.String(256), nullable=False),
        sa.Column("deleted_ids_digest", sa.String(64), nullable=False),
        sa.Column("recorded_at", sa.String(64), nullable=False, index=True),
    )
    op.create_table(
        "data_legal_holds",
        sa.Column("hold_id", sa.String(64), primary_key=True),
        sa.Column("family_id", sa.String(128), nullable=False, index=True),
        sa.Column("key_type", sa.String(32), nullable=False),
        sa.Column("key_value", sa.String(256), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("placed_by", sa.String(256), nullable=False),
        sa.Column("placed_at", sa.String(64), nullable=False),
        sa.Column("released_at", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("data_legal_holds")
    op.drop_table("data_lifecycle_events")
