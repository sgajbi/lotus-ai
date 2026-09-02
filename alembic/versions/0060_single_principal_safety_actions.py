"""single principal safety actions

Revision ID: 0060_single_principal_safety_actions
Revises: 0059_add_governed_actions
Create Date: 2026-09-02

Issue #157: a safety-increasing action (kill-switch activation, prompt
rollback) takes one verified principal and no approver - a human handoff
inside an emergency stop would make the platform less safe. The approver
columns become nullable so those records can say honestly that no approval
existed, instead of carrying a caller-typed name as if it were one.

The batch alters carry complete ``copy_from`` tables so the offline
``alembic upgrade --sql`` contract check can generate the SQLite
move-and-copy script without a live database to reflect.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0060_single_principal_safety_actions"
down_revision = "0059_add_governed_actions"
branch_labels = None
depends_on = None


def _kill_switch_activations() -> sa.Table:
    return sa.Table(
        "kill_switch_activations",
        sa.MetaData(),
        sa.Column("switch_id", sa.String(64), primary_key=True),
        sa.Column("scope", sa.String(32), nullable=False, index=True),
        sa.Column("semantics", sa.String(16), nullable=False, server_default="HARD_KILL"),
        sa.Column("target", sa.String(256), nullable=True, index=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.String(128), nullable=False),
        sa.Column("approved_by", sa.String(128), nullable=False),
        sa.Column("activated_at", sa.String(64), nullable=False, index=True),
        sa.Column("expires_at_utc", sa.String(64), nullable=True),
        sa.Column("expiry_recorded_at", sa.String(64), nullable=True),
        sa.Column("cleared_at", sa.String(64), nullable=True, index=True),
        sa.Column("cleared_by", sa.String(128), nullable=True),
        sa.Column("clear_reason", sa.Text(), nullable=True),
    )


def _prompt_rollout_events() -> sa.Table:
    return sa.Table(
        "prompt_rollout_events",
        sa.MetaData(),
        sa.Column("event_id", sa.String(128), primary_key=True),
        sa.Column("task_id", sa.String(128), nullable=False, index=True),
        sa.Column("action_type", sa.String(64), nullable=False, index=True),
        sa.Column("requested_by", sa.String(256), nullable=False),
        sa.Column("approved_by", sa.String(256), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("prior_active_prompt_version", sa.String(128), nullable=True),
        sa.Column("resulting_active_prompt_version", sa.String(128), nullable=True),
        sa.Column("prior_candidate_prompt_version", sa.String(128), nullable=True),
        sa.Column("resulting_candidate_prompt_version", sa.String(128), nullable=True),
        sa.Column("authorization_payload", sa.JSON(), nullable=True),
        sa.Column("recorded_at", sa.String(64), nullable=False, index=True),
    )


def upgrade() -> None:
    with op.batch_alter_table(
        "kill_switch_activations", copy_from=_kill_switch_activations()
    ) as batch:
        batch.alter_column("approved_by", existing_type=sa.String(length=128), nullable=True)
    with op.batch_alter_table("prompt_rollout_events", copy_from=_prompt_rollout_events()) as batch:
        batch.alter_column("approved_by", existing_type=sa.String(length=256), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("prompt_rollout_events") as batch:
        batch.alter_column("approved_by", existing_type=sa.String(length=256), nullable=False)
    with op.batch_alter_table("kill_switch_activations") as batch:
        batch.alter_column("approved_by", existing_type=sa.String(length=128), nullable=False)
