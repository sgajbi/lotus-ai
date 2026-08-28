"""add synchronous workflow-pack execution idempotency

Revision ID: 0041_add_workflow_pack_execution_idempotency
Revises: 0040_scope_audit_record_reads
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0041_add_workflow_pack_execution_idempotency"
down_revision = "0040_scope_audit_record_reads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_pack_execution_idempotency",
        sa.Column("record_id", sa.String(length=96), nullable=False),
        sa.Column("caller_app", sa.String(length=128), nullable=False),
        sa.Column("tenant_scope", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("owner_token", sa.String(length=64), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("record_id"),
        sa.UniqueConstraint(
            "caller_app",
            "tenant_scope",
            "idempotency_key",
            name="uq_workflow_pack_execution_idempotency_scope",
        ),
    )
    op.create_index(
        "ix_workflow_pack_execution_idempotency_state",
        "workflow_pack_execution_idempotency",
        ["state"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_execution_idempotency_updated_at",
        "workflow_pack_execution_idempotency",
        ["updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_pack_execution_idempotency_updated_at",
        table_name="workflow_pack_execution_idempotency",
    )
    op.drop_index(
        "ix_workflow_pack_execution_idempotency_state",
        table_name="workflow_pack_execution_idempotency",
    )
    op.drop_table("workflow_pack_execution_idempotency")
