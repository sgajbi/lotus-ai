"""add control event authorization payloads

Revision ID: 0021_add_control_event_authorization_payloads
Revises: 0020_add_audit_authorization_payload
Create Date: 2026-03-24 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0021_add_control_event_authorization_payloads"
down_revision = "0020_add_audit_authorization_payload"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "async_control_events",
        sa.Column("authorization_payload", sa.JSON(), nullable=True),
    )
    op.add_column(
        "prompt_rollout_events",
        sa.Column("authorization_payload", sa.JSON(), nullable=True),
    )
    op.add_column(
        "provider_operations_events",
        sa.Column("authorization_payload", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("provider_operations_events", "authorization_payload")
    op.drop_column("prompt_rollout_events", "authorization_payload")
    op.drop_column("async_control_events", "authorization_payload")
