"""add model revision drift observations

Revision ID: 0047_add_model_revision_drift
Revises: 0046_add_model_lifecycle_events
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0047_add_model_revision_drift"
down_revision = "0046_add_model_lifecycle_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_revision_drift_observations",
        sa.Column("observation_id", sa.String(length=128), nullable=False),
        sa.Column("entry_id", sa.String(length=256), nullable=False),
        sa.Column("expected_identity", sa.String(length=256), nullable=False),
        sa.Column("observed_model_id", sa.String(length=256), nullable=False),
        sa.Column("revision_pinned_at_observation", sa.Boolean(), nullable=False),
        sa.Column("first_observed_at", sa.String(length=64), nullable=False),
        sa.Column("last_observed_at", sa.String(length=64), nullable=False),
        sa.Column("observation_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("observation_id"),
    )
    op.create_index(
        "ix_model_revision_drift_observations_entry_id",
        "model_revision_drift_observations",
        ["entry_id"],
        unique=False,
    )
    op.create_index(
        "ix_model_revision_drift_observations_last_observed_at",
        "model_revision_drift_observations",
        ["last_observed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_model_revision_drift_observations_last_observed_at",
        table_name="model_revision_drift_observations",
    )
    op.drop_index(
        "ix_model_revision_drift_observations_entry_id",
        table_name="model_revision_drift_observations",
    )
    op.drop_table("model_revision_drift_observations")
