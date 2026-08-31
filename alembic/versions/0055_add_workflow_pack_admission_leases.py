"""add replica-shared workflow-pack admission leases

Revision ID: 0055_add_workflow_pack_admission_leases
Revises: 0054_add_audit_cost_identity
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0055_add_workflow_pack_admission_leases"
down_revision = "0054_add_audit_cost_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_pack_admission_leases",
        sa.Column("queue_item_id", sa.String(length=128), primary_key=True),
        sa.Column("policy_id", sa.String(length=128), nullable=False, index=True),
        sa.Column("workflow_pack_id", sa.String(length=128), nullable=False),
        sa.Column("workflow_pack_version", sa.String(length=64), nullable=False),
        sa.Column("lane", sa.String(length=64), nullable=False, index=True),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("admitted_at", sa.String(length=64), nullable=False, index=True),
        sa.Column("caller_app", sa.String(length=128), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=True),
        sa.Column("workflow_surface", sa.String(length=128), nullable=True),
        sa.Column("artifact_refs_payload", sa.JSON(), nullable=False),
    )
    op.create_table(
        "workflow_pack_admission_guards",
        sa.Column("policy_id", sa.String(length=128), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("workflow_pack_admission_guards")
    op.drop_table("workflow_pack_admission_leases")
