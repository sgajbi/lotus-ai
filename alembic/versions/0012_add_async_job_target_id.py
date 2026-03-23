"""add async job target id

Revision ID: 0012_add_async_job_target_id
Revises: 0011_add_async_runtime_state_tables
Create Date: 2026-03-23 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0012_add_async_job_target_id"
down_revision = "0011_add_async_runtime_state_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("async_jobs", sa.Column("target_id", sa.String(length=128), nullable=True))
    op.create_index("ix_async_jobs_target_id", "async_jobs", ["target_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_async_jobs_target_id", table_name="async_jobs")
    op.drop_column("async_jobs", "target_id")
