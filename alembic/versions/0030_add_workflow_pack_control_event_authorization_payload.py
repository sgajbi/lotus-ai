"""add workflow pack control event authorization payload

Revision ID: 0030_add_workflow_pack_control_event_authorization_payload
Revises: 0029_add_workflow_pack_registry_state_tables
Create Date: 2026-04-19 17:10:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0030_add_workflow_pack_control_event_authorization_payload"
down_revision = "0029_add_workflow_pack_registry_state_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workflow_pack_control_events",
        sa.Column("authorization_payload", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workflow_pack_control_events", "authorization_payload")
