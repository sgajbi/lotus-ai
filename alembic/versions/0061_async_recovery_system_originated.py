"""async recovery is system originated

Revision ID: 0061_async_recovery_system_originated
Revises: 0060_single_principal_safety_actions
Create Date: 2026-09-02

Issue #157, final slice: runtime-originated queue recovery answers to a
service identity and has no approver. The approver column becomes nullable so
those events say honestly that no approval existed, instead of carrying
"lotus-ai.async-worker-runtime" dressed up as one; the governed-action record
(actor class SYSTEM_ORIGINATED) is the evidence of what acted.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0061_async_recovery_system_originated"
down_revision = "0060_single_principal_safety_actions"
branch_labels = None
depends_on = None


def _async_control_events() -> sa.Table:
    return sa.Table(
        "async_control_events",
        sa.MetaData(),
        sa.Column("event_id", sa.String(128), primary_key=True),
        sa.Column("job_id", sa.String(128), nullable=False, index=True),
        sa.Column("action_type", sa.String(64), nullable=False, index=True),
        sa.Column("requested_by", sa.String(256), nullable=False),
        sa.Column("approved_by", sa.String(256), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("prior_status", sa.String(64), nullable=False),
        sa.Column("resulting_status", sa.String(64), nullable=False),
        sa.Column("affected_attempt_id", sa.String(128), nullable=True),
        sa.Column("authorization_payload", sa.JSON(), nullable=True),
        sa.Column("recorded_at", sa.String(64), nullable=False, index=True),
    )


def upgrade() -> None:
    with op.batch_alter_table("async_control_events", copy_from=_async_control_events()) as batch:
        batch.alter_column("approved_by", existing_type=sa.String(length=256), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("async_control_events") as batch:
        batch.alter_column("approved_by", existing_type=sa.String(length=256), nullable=False)
