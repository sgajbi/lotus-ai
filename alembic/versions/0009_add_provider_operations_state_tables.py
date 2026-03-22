"""add provider operations state tables

Revision ID: 0009_add_provider_operations_state_tables
Revises: 0008_enable_catalog_only_retrieval_sources
Create Date: 2026-03-23 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_add_provider_operations_state_tables"
down_revision = "0008_enable_catalog_only_retrieval_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_quota_state",
        sa.Column("scope", sa.String(length=32), primary_key=True, nullable=False),
        sa.Column("scope_key", sa.String(length=256), primary_key=True, nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.String(length=64), nullable=False),
    )
    op.create_table(
        "provider_budget_state",
        sa.Column("budget_key", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("current_spend_usd", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.String(length=64), nullable=False),
    )
    op.create_table(
        "provider_degradation_state",
        sa.Column("degradation_key", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("consecutive_failure_count", sa.Integer(), nullable=False),
        sa.Column("last_failure_category", sa.String(length=64), nullable=True),
        sa.Column("circuit_open_until", sa.String(length=64), nullable=True),
        sa.Column("timeout_failure_count", sa.Integer(), nullable=False),
        sa.Column("rate_limited_failure_count", sa.Integer(), nullable=False),
        sa.Column("upstream_error_failure_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.String(length=64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("provider_degradation_state")
    op.drop_table("provider_budget_state")
    op.drop_table("provider_quota_state")
