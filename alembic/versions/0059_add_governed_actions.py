"""add governed actions table

Revision ID: 0059_add_governed_actions
Revises: 0058_add_audit_access_denial_reason
Create Date: 2026-09-02

Issue #157 S1: immutable evidence for governed control-plane actions -
requester credential, distinct approver credential, action hash, and the
request/approval/execution instants. First consumer: kill-switch clearance.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0059_add_governed_actions"
down_revision = "0058_add_audit_access_denial_reason"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_governed_actions",
        sa.Column("action_id", sa.String(length=64), primary_key=True),
        sa.Column("action_type", sa.String(length=64), nullable=False, index=True),
        sa.Column("actor_class", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, index=True),
        sa.Column("target", sa.String(length=256), nullable=False, index=True),
        sa.Column("action_hash", sa.String(length=64), nullable=False),
        sa.Column("action_payload", sa.JSON(), nullable=False),
        sa.Column("requester_caller_app", sa.String(length=128), nullable=False),
        sa.Column("requester_trust_source", sa.String(length=64), nullable=False),
        sa.Column("requester_key_id", sa.String(length=128), nullable=True),
        sa.Column("requester_attribution", sa.String(length=256), nullable=True),
        sa.Column("requested_at", sa.String(length=64), nullable=False),
        sa.Column("approver_caller_app", sa.String(length=128), nullable=True),
        sa.Column("approver_trust_source", sa.String(length=64), nullable=True),
        sa.Column("approver_key_id", sa.String(length=128), nullable=True),
        sa.Column("approver_attribution", sa.String(length=256), nullable=True),
        sa.Column("approved_at", sa.String(length=64), nullable=True),
        sa.Column("executed_at", sa.String(length=64), nullable=True),
        sa.Column("superseded_by_action_id", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("provider_governed_actions")
