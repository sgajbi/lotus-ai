"""add model catalogue entries

Revision ID: 0042_add_model_catalogue
Revises: 0041_add_workflow_pack_execution_idempotency
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0042_add_model_catalogue"
down_revision = "0041_add_workflow_pack_execution_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_catalogue_entries",
        sa.Column("entry_id", sa.String(length=256), nullable=False),
        sa.Column("provider_id", sa.String(length=128), nullable=False),
        sa.Column("provider_mode", sa.String(length=64), nullable=False),
        sa.Column("model_family", sa.String(length=128), nullable=False),
        sa.Column("model_revision", sa.String(length=128), nullable=False),
        sa.Column("deployment", sa.String(length=128), nullable=True),
        sa.Column("sku", sa.String(length=128), nullable=True),
        sa.Column("lifecycle_state", sa.String(length=32), nullable=False),
        sa.Column("revision_pinned", sa.Boolean(), nullable=False),
        sa.Column("modalities", sa.JSON(), nullable=False),
        sa.Column("context_window_tokens", sa.Integer(), nullable=True),
        sa.Column("max_output_tokens", sa.Integer(), nullable=True),
        sa.Column("supports_structured_output", sa.Boolean(), nullable=True),
        sa.Column("supports_tool_calling", sa.Boolean(), nullable=True),
        sa.Column("supports_streaming", sa.Boolean(), nullable=True),
        sa.Column("approved_workflow_pack_ids", sa.JSON(), nullable=False),
        sa.Column("approval_evidence_refs", sa.JSON(), nullable=False),
        sa.Column("approved_from_utc", sa.String(length=64), nullable=True),
        sa.Column("approved_until_utc", sa.String(length=64), nullable=True),
        sa.Column("seed_source", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("last_updated_at", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("entry_id"),
    )
    op.create_index(
        "ix_model_catalogue_entries_provider_id",
        "model_catalogue_entries",
        ["provider_id"],
        unique=False,
    )
    op.create_index(
        "ix_model_catalogue_entries_model_family",
        "model_catalogue_entries",
        ["model_family"],
        unique=False,
    )
    op.create_index(
        "ix_model_catalogue_entries_lifecycle_state",
        "model_catalogue_entries",
        ["lifecycle_state"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_model_catalogue_entries_lifecycle_state",
        table_name="model_catalogue_entries",
    )
    op.drop_index(
        "ix_model_catalogue_entries_model_family",
        table_name="model_catalogue_entries",
    )
    op.drop_index(
        "ix_model_catalogue_entries_provider_id",
        table_name="model_catalogue_entries",
    )
    op.drop_table("model_catalogue_entries")
