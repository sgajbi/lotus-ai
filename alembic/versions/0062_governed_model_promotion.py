"""governed model promotion

Revision ID: 0062_governed_model_promotion
Revises: 0061_async_recovery_system_originated
Create Date: 2026-09-03

Issue #245: lifecycle transitions follow the risk direction. A transition
that expands serving posture is governed two-step through the primitive; a
safety or administrative transition takes one verified principal and no
approver. The approver column becomes nullable so single-principal
transitions say honestly that no approval existed.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0062_governed_model_promotion"
down_revision = "0061_async_recovery_system_originated"
branch_labels = None
depends_on = None


def _lifecycle_events() -> sa.Table:
    return sa.Table(
        "model_catalogue_lifecycle_events",
        sa.MetaData(),
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("entry_id", sa.String(256), nullable=False, index=True),
        sa.Column("from_state", sa.String(32), nullable=False),
        sa.Column("to_state", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.String(128), nullable=False),
        sa.Column("approved_by", sa.String(128), nullable=False),
        sa.Column("approval_evidence_ref", sa.String(256), nullable=True),
        sa.Column("recorded_at", sa.String(64), nullable=False, index=True),
    )


def upgrade() -> None:
    with op.batch_alter_table(
        "model_catalogue_lifecycle_events", copy_from=_lifecycle_events()
    ) as batch:
        batch.alter_column("approved_by", existing_type=sa.String(length=128), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("model_catalogue_lifecycle_events") as batch:
        batch.alter_column("approved_by", existing_type=sa.String(length=128), nullable=False)
