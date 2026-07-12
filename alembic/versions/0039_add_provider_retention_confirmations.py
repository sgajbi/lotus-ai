"""add provider retention confirmations

Revision ID: 0039_add_provider_retention_confirmations
Revises: 0038_add_workflow_run_model_approval_ref
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0039_add_provider_retention_confirmations"
down_revision = "0038_add_workflow_run_model_approval_ref"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_retention_confirmations",
        sa.Column("confirmation_id", sa.String(length=128), nullable=False),
        sa.Column("workflow_run_id", sa.String(length=128), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("provider_confirmation_ref", sa.String(length=256), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=64), nullable=False),
        sa.Column("envelope_payload", sa.JSON(), nullable=False),
        sa.Column("recorded_at", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("confirmation_id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("provider_confirmation_ref"),
    )
    op.create_index(
        "ix_provider_retention_confirmations_workflow_run_id",
        "provider_retention_confirmations",
        ["workflow_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_provider_retention_confirmations_tenant_id",
        "provider_retention_confirmations",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_provider_retention_confirmations_outcome",
        "provider_retention_confirmations",
        ["outcome"],
        unique=False,
    )
    op.create_index(
        "ix_provider_retention_confirmations_recorded_at",
        "provider_retention_confirmations",
        ["recorded_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_provider_retention_confirmations_recorded_at",
        table_name="provider_retention_confirmations",
    )
    op.drop_index(
        "ix_provider_retention_confirmations_outcome",
        table_name="provider_retention_confirmations",
    )
    op.drop_index(
        "ix_provider_retention_confirmations_tenant_id",
        table_name="provider_retention_confirmations",
    )
    op.drop_index(
        "ix_provider_retention_confirmations_workflow_run_id",
        table_name="provider_retention_confirmations",
    )
    op.drop_table("provider_retention_confirmations")
