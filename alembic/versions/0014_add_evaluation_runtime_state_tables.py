"""add evaluation runtime state tables

Revision ID: 0014_add_evaluation_runtime_state_tables
Revises: 0013_add_async_control_events
Create Date: 2026-03-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0014_add_evaluation_runtime_state_tables"
down_revision = "0013_add_async_control_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evaluation_runs",
        sa.Column("run_id", sa.String(length=128), primary_key=True, nullable=False),
        sa.Column("fixture_id", sa.String(length=128), nullable=False),
        sa.Column("manifest_version", sa.String(length=64), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=64), nullable=False),
        sa.Column("triggered_by", sa.String(length=256), nullable=False),
        sa.Column("submitted_at", sa.String(length=64), nullable=False),
        sa.Column("async_job_id", sa.String(length=128), nullable=True),
        sa.Column("latest_message", sa.Text(), nullable=False),
        sa.Column("verdict", sa.String(length=64), nullable=True),
        sa.Column("case_count", sa.Integer(), nullable=False),
    )
    op.create_index("ix_evaluation_runs_fixture_id", "evaluation_runs", ["fixture_id"])
    op.create_index(
        "ix_evaluation_runs_lifecycle_status",
        "evaluation_runs",
        ["lifecycle_status"],
    )
    op.create_index("ix_evaluation_runs_submitted_at", "evaluation_runs", ["submitted_at"])
    op.create_index("ix_evaluation_runs_async_job_id", "evaluation_runs", ["async_job_id"])

    op.create_table(
        "evaluation_run_attempts",
        sa.Column("attempt_id", sa.String(length=128), primary_key=True, nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.String(length=64), nullable=True),
        sa.Column("completed_at", sa.String(length=64), nullable=True),
        sa.Column("worker_id", sa.String(length=128), nullable=True),
        sa.Column("latest_message", sa.Text(), nullable=False),
        sa.Column("verdict", sa.String(length=64), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["evaluation_runs.run_id"]),
    )
    op.create_index("ix_evaluation_run_attempts_run_id", "evaluation_run_attempts", ["run_id"])
    op.create_index(
        "ix_evaluation_run_attempts_lifecycle_status",
        "evaluation_run_attempts",
        ["lifecycle_status"],
    )

    op.create_table(
        "evaluation_case_results",
        sa.Column("case_result_id", sa.String(length=128), primary_key=True, nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("attempt_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("fixture_id", sa.String(length=128), nullable=False),
        sa.Column("outcome", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("recorded_at", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["evaluation_runs.run_id"]),
    )
    op.create_index("ix_evaluation_case_results_run_id", "evaluation_case_results", ["run_id"])
    op.create_index(
        "ix_evaluation_case_results_attempt_id",
        "evaluation_case_results",
        ["attempt_id"],
    )
    op.create_index(
        "ix_evaluation_case_results_fixture_id",
        "evaluation_case_results",
        ["fixture_id"],
    )
    op.create_index("ix_evaluation_case_results_outcome", "evaluation_case_results", ["outcome"])
    op.create_index(
        "ix_evaluation_case_results_recorded_at",
        "evaluation_case_results",
        ["recorded_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_evaluation_case_results_recorded_at", table_name="evaluation_case_results")
    op.drop_index("ix_evaluation_case_results_outcome", table_name="evaluation_case_results")
    op.drop_index("ix_evaluation_case_results_fixture_id", table_name="evaluation_case_results")
    op.drop_index("ix_evaluation_case_results_attempt_id", table_name="evaluation_case_results")
    op.drop_index("ix_evaluation_case_results_run_id", table_name="evaluation_case_results")
    op.drop_table("evaluation_case_results")

    op.drop_index(
        "ix_evaluation_run_attempts_lifecycle_status",
        table_name="evaluation_run_attempts",
    )
    op.drop_index("ix_evaluation_run_attempts_run_id", table_name="evaluation_run_attempts")
    op.drop_table("evaluation_run_attempts")

    op.drop_index("ix_evaluation_runs_async_job_id", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_submitted_at", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_lifecycle_status", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_fixture_id", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")

