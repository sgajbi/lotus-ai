"""add async runtime state tables

Revision ID: 0011_add_async_runtime_state_tables
Revises: 0010_add_provider_operations_events
Create Date: 2026-03-23 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_add_async_runtime_state_tables"
down_revision: str | Sequence[str] | None = "0010_add_provider_operations_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "async_jobs",
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("job_type", sa.String(length=128), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=64), nullable=False),
        sa.Column("submitted_at", sa.String(length=64), nullable=False),
        sa.Column("caller_app", sa.String(length=128), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("payload_summary", sa.Text(), nullable=False),
        sa.Column("execution_path", sa.String(length=128), nullable=False),
        sa.Column("related_evaluation_run_id", sa.String(length=128), nullable=True),
        sa.Column("latest_message", sa.Text(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index("ix_async_jobs_job_type", "async_jobs", ["job_type"], unique=False)
    op.create_index(
        "ix_async_jobs_lifecycle_status",
        "async_jobs",
        ["lifecycle_status"],
        unique=False,
    )
    op.create_index("ix_async_jobs_submitted_at", "async_jobs", ["submitted_at"], unique=False)

    op.create_table(
        "async_job_attempts",
        sa.Column("attempt_id", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=64), nullable=False),
        sa.Column("worker_id", sa.String(length=128), nullable=True),
        sa.Column("claimed_at", sa.String(length=64), nullable=True),
        sa.Column("heartbeat_at", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.String(length=64), nullable=True),
        sa.Column("completed_at", sa.String(length=64), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("recorded_message", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["async_jobs.job_id"]),
        sa.PrimaryKeyConstraint("attempt_id"),
    )
    op.create_index("ix_async_job_attempts_job_id", "async_job_attempts", ["job_id"], unique=False)
    op.create_index(
        "ix_async_job_attempts_lifecycle_status",
        "async_job_attempts",
        ["lifecycle_status"],
        unique=False,
    )

    op.create_table(
        "async_worker_leases",
        sa.Column("lease_id", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("attempt_id", sa.String(length=128), nullable=False),
        sa.Column("worker_id", sa.String(length=128), nullable=False),
        sa.Column("claimed_at", sa.String(length=64), nullable=False),
        sa.Column("heartbeat_at", sa.String(length=64), nullable=False),
        sa.Column("lease_expires_at", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["async_jobs.job_id"]),
        sa.PrimaryKeyConstraint("lease_id"),
    )
    op.create_index(
        "ix_async_worker_leases_job_id", "async_worker_leases", ["job_id"], unique=False
    )
    op.create_index(
        "ix_async_worker_leases_attempt_id",
        "async_worker_leases",
        ["attempt_id"],
        unique=False,
    )
    op.create_index(
        "ix_async_worker_leases_lease_expires_at",
        "async_worker_leases",
        ["lease_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_async_worker_leases_lease_expires_at", table_name="async_worker_leases")
    op.drop_index("ix_async_worker_leases_attempt_id", table_name="async_worker_leases")
    op.drop_index("ix_async_worker_leases_job_id", table_name="async_worker_leases")
    op.drop_table("async_worker_leases")

    op.drop_index("ix_async_job_attempts_lifecycle_status", table_name="async_job_attempts")
    op.drop_index("ix_async_job_attempts_job_id", table_name="async_job_attempts")
    op.drop_table("async_job_attempts")

    op.drop_index("ix_async_jobs_submitted_at", table_name="async_jobs")
    op.drop_index("ix_async_jobs_lifecycle_status", table_name="async_jobs")
    op.drop_index("ix_async_jobs_job_type", table_name="async_jobs")
    op.drop_table("async_jobs")
