"""scope audit record reads

Revision ID: 0040_scope_audit_record_reads
Revises: 0039_add_provider_retention_confirmations
Create Date: 2026-08-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0040_scope_audit_record_reads"
down_revision = "0039_add_provider_retention_confirmations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "caller_policies",
        sa.Column(
            "allow_audit_read_all_tenants",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.execute(
        "UPDATE caller_policies SET allow_audit_read_all_tenants = TRUE "
        "WHERE caller_app = 'lotus-platform'"
    )
    op.create_table(
        "audit_access_events",
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("caller_app", sa.String(length=128), nullable=False),
        sa.Column("caller_trust_source", sa.String(length=64), nullable=False),
        sa.Column("scope_mode", sa.String(length=32), nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("returned_record_count", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_audit_access_events_caller_app",
        "audit_access_events",
        ["caller_app"],
        unique=False,
    )
    op.create_index(
        "ix_audit_access_events_recorded_at",
        "audit_access_events",
        ["recorded_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_audit_access_events_recorded_at", table_name="audit_access_events")
    op.drop_index("ix_audit_access_events_caller_app", table_name="audit_access_events")
    op.drop_table("audit_access_events")
    op.drop_column("caller_policies", "allow_audit_read_all_tenants")
