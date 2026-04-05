"""add prompt rollout state tables

Revision ID: 0016_add_prompt_rollout_state_tables
Revises: 0015_add_audit_execution_outcome_payload
Create Date: 2026-03-23 00:00:00.000000
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0016_add_prompt_rollout_state_tables"
down_revision = "0015_add_audit_execution_outcome_payload"
branch_labels = None
depends_on = None

_SEEDED_CREATED_AT = datetime(2026, 3, 23, tzinfo=UTC).isoformat()


def upgrade() -> None:
    op.create_table(
        "prompt_definition_versions",
        sa.Column("task_id", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=128), nullable=False),
        sa.Column("prompt_kind", sa.String(length=64), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=32), nullable=False),
        sa.Column("management_mode", sa.String(length=32), nullable=False),
        sa.Column("source_reference", sa.Text(), nullable=False),
        sa.Column("system_instructions", sa.Text(), nullable=False),
        sa.Column("output_contract_notes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("task_id", "prompt_version"),
    )
    op.create_index(
        "ix_prompt_definition_versions_created_at",
        "prompt_definition_versions",
        ["created_at"],
    )

    op.create_table(
        "prompt_rollout_state",
        sa.Column("task_id", sa.String(length=128), nullable=False),
        sa.Column("active_prompt_version", sa.String(length=128), nullable=False),
        sa.Column("candidate_prompt_version", sa.String(length=128), nullable=True),
        sa.Column("previous_active_prompt_version", sa.String(length=128), nullable=True),
        sa.Column("rollout_mode", sa.String(length=64), nullable=False),
        sa.Column("runtime_mutation_enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("task_id"),
    )
    op.create_index("ix_prompt_rollout_state_updated_at", "prompt_rollout_state", ["updated_at"])

    op.create_table(
        "prompt_rollout_events",
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("task_id", sa.String(length=128), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("requested_by", sa.String(length=256), nullable=False),
        sa.Column("approved_by", sa.String(length=256), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("prior_active_prompt_version", sa.String(length=128), nullable=True),
        sa.Column("resulting_active_prompt_version", sa.String(length=128), nullable=True),
        sa.Column("prior_candidate_prompt_version", sa.String(length=128), nullable=True),
        sa.Column("resulting_candidate_prompt_version", sa.String(length=128), nullable=True),
        sa.Column("recorded_at", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("ix_prompt_rollout_events_task_id", "prompt_rollout_events", ["task_id"])
    op.create_index(
        "ix_prompt_rollout_events_action_type", "prompt_rollout_events", ["action_type"]
    )
    op.create_index(
        "ix_prompt_rollout_events_recorded_at", "prompt_rollout_events", ["recorded_at"]
    )

    op.execute(
        sa.text(
            """
            INSERT INTO prompt_definition_versions (
                task_id,
                prompt_version,
                prompt_kind,
                lifecycle_status,
                management_mode,
                source_reference,
                system_instructions,
                output_contract_notes,
                created_at
            )
            SELECT
                task_id,
                prompt_version,
                prompt_kind,
                lifecycle_status,
                management_mode,
                source_reference,
                system_instructions,
                output_contract_notes,
                :created_at
            FROM prompt_definitions
            """
        ).bindparams(created_at=_SEEDED_CREATED_AT)
    )
    op.execute(
        sa.text(
            """
            INSERT INTO prompt_rollout_state (
                task_id,
                active_prompt_version,
                candidate_prompt_version,
                previous_active_prompt_version,
                rollout_mode,
                runtime_mutation_enabled,
                updated_at
            )
            SELECT
                task_id,
                prompt_version,
                NULL,
                NULL,
                'GOVERNED_STATE_READ_ONLY',
                FALSE,
                :updated_at
            FROM prompt_definitions
            """
        ).bindparams(updated_at=_SEEDED_CREATED_AT)
    )


def downgrade() -> None:
    op.drop_index("ix_prompt_rollout_events_recorded_at", table_name="prompt_rollout_events")
    op.drop_index("ix_prompt_rollout_events_action_type", table_name="prompt_rollout_events")
    op.drop_index("ix_prompt_rollout_events_task_id", table_name="prompt_rollout_events")
    op.drop_table("prompt_rollout_events")

    op.drop_index("ix_prompt_rollout_state_updated_at", table_name="prompt_rollout_state")
    op.drop_table("prompt_rollout_state")

    op.drop_index(
        "ix_prompt_definition_versions_created_at", table_name="prompt_definition_versions"
    )
    op.drop_table("prompt_definition_versions")
