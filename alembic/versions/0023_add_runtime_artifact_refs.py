"""add runtime artifact refs

Revision ID: 0023_add_runtime_artifact_refs
Revises: 0022_add_artifact_metadata_tables
Create Date: 2026-03-24 20:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0023_add_runtime_artifact_refs"
down_revision = "0022_add_artifact_metadata_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "async_jobs",
        sa.Column("artifact_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "evaluation_case_results",
        sa.Column("artifact_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )


def downgrade() -> None:
    op.drop_column("evaluation_case_results", "artifact_ids")
    op.drop_column("async_jobs", "artifact_ids")
