"""add artifact metadata tables

Revision ID: 0022_add_artifact_metadata_tables
Revises: 0021_add_control_event_authorization_payloads
Create Date: 2026-03-24 18:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0022_add_artifact_metadata_tables"
down_revision = "0021_add_control_event_authorization_payloads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "artifact_metadata",
        sa.Column("artifact_id", sa.String(length=128), nullable=False),
        sa.Column("domain", sa.String(length=64), nullable=False),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("source_object_kind", sa.String(length=64), nullable=False),
        sa.Column("source_object_id", sa.String(length=128), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=32), nullable=False),
        sa.Column("retention_posture", sa.String(length=32), nullable=False),
        sa.Column("media_type", sa.String(length=128), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_backend", sa.String(length=32), nullable=False),
        sa.Column("storage_reference", sa.Text(), nullable=False),
        sa.Column("lineage_parent_artifact_id", sa.String(length=128), nullable=True),
        sa.Column("superseded_by_artifact_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint("artifact_id"),
    )
    op.create_index("ix_artifact_metadata_domain", "artifact_metadata", ["domain"], unique=False)
    op.create_index(
        "ix_artifact_metadata_source_object_kind_source_object_id",
        "artifact_metadata",
        ["source_object_kind", "source_object_id"],
        unique=False,
    )
    op.create_index(
        "ix_artifact_metadata_created_at",
        "artifact_metadata",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_artifact_metadata_created_at", table_name="artifact_metadata")
    op.drop_index(
        "ix_artifact_metadata_source_object_kind_source_object_id",
        table_name="artifact_metadata",
    )
    op.drop_index("ix_artifact_metadata_domain", table_name="artifact_metadata")
    op.drop_table("artifact_metadata")
