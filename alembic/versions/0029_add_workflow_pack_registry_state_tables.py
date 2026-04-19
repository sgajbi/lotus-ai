"""add workflow pack registry state tables

Revision ID: 0029_add_workflow_pack_registry_state_tables
Revises: 0028_add_workflow_pack_run_ledger_tables
Create Date: 2026-04-19 12:20:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0029_add_workflow_pack_registry_state_tables"
down_revision = "0028_add_workflow_pack_run_ledger_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_pack_registrations",
        sa.Column("pack_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("pack_family", sa.String(length=128), nullable=False),
        sa.Column("owner_repository", sa.String(length=128), nullable=False),
        sa.Column("owner_service", sa.String(length=128), nullable=False),
        sa.Column(
            "truth_owner_services",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("primary_use_case", sa.String(length=128), nullable=False),
        sa.Column("workflow_authority_owner", sa.String(length=128), nullable=False),
        sa.Column("default_execution_mode", sa.String(length=32), nullable=False),
        sa.Column("definition_ref", sa.Text(), nullable=False),
        sa.Column("definition_refs", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("compatibility_contract_version", sa.String(length=64), nullable=False),
        sa.Column("registration_status", sa.String(length=32), nullable=False),
        sa.Column("activation_state", sa.String(length=32), nullable=False),
        sa.Column("registered_definition_digest", sa.String(length=128), nullable=False),
        sa.Column("supported_callers", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column(
            "supported_identity_classes",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "supported_environments",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("tenant_scope", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("surface_scope", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("default_rollout_stage", sa.String(length=64), nullable=False),
        sa.Column("pause_state", sa.String(length=64), nullable=False),
        sa.Column("supersedes", sa.String(length=256), nullable=True),
        sa.Column("superseded_by", sa.String(length=256), nullable=True),
        sa.Column("registered_at", sa.String(length=64), nullable=False),
        sa.Column("registered_by", sa.String(length=128), nullable=False),
        sa.Column("last_activated_at", sa.String(length=64), nullable=True),
        sa.Column("last_changed_at", sa.String(length=64), nullable=False),
        sa.Column("status_summary", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.PrimaryKeyConstraint("pack_id", "version"),
    )
    op.create_index(
        "ix_workflow_pack_registrations_pack_family",
        "workflow_pack_registrations",
        ["pack_family"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_registrations_owner_repository",
        "workflow_pack_registrations",
        ["owner_repository"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_registrations_primary_use_case",
        "workflow_pack_registrations",
        ["primary_use_case"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_registrations_registration_status",
        "workflow_pack_registrations",
        ["registration_status"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_registrations_activation_state",
        "workflow_pack_registrations",
        ["activation_state"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_registrations_registered_at",
        "workflow_pack_registrations",
        ["registered_at"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_registrations_last_changed_at",
        "workflow_pack_registrations",
        ["last_changed_at"],
        unique=False,
    )

    op.create_table(
        "workflow_pack_control_events",
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("pack_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("approved_by", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("prior_registration_status", sa.String(length=32), nullable=False),
        sa.Column("resulting_registration_status", sa.String(length=32), nullable=False),
        sa.Column("prior_activation_state", sa.String(length=32), nullable=False),
        sa.Column("resulting_activation_state", sa.String(length=32), nullable=False),
        sa.Column("caller_app", sa.String(length=128), nullable=False),
        sa.Column("recorded_at", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_workflow_pack_control_events_pack_id",
        "workflow_pack_control_events",
        ["pack_id"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_control_events_version",
        "workflow_pack_control_events",
        ["version"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_control_events_action_type",
        "workflow_pack_control_events",
        ["action_type"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_pack_control_events_recorded_at",
        "workflow_pack_control_events",
        ["recorded_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_pack_control_events_recorded_at",
        table_name="workflow_pack_control_events",
    )
    op.drop_index(
        "ix_workflow_pack_control_events_action_type",
        table_name="workflow_pack_control_events",
    )
    op.drop_index(
        "ix_workflow_pack_control_events_version",
        table_name="workflow_pack_control_events",
    )
    op.drop_index(
        "ix_workflow_pack_control_events_pack_id",
        table_name="workflow_pack_control_events",
    )
    op.drop_table("workflow_pack_control_events")

    op.drop_index(
        "ix_workflow_pack_registrations_last_changed_at",
        table_name="workflow_pack_registrations",
    )
    op.drop_index(
        "ix_workflow_pack_registrations_registered_at",
        table_name="workflow_pack_registrations",
    )
    op.drop_index(
        "ix_workflow_pack_registrations_activation_state",
        table_name="workflow_pack_registrations",
    )
    op.drop_index(
        "ix_workflow_pack_registrations_registration_status",
        table_name="workflow_pack_registrations",
    )
    op.drop_index(
        "ix_workflow_pack_registrations_primary_use_case",
        table_name="workflow_pack_registrations",
    )
    op.drop_index(
        "ix_workflow_pack_registrations_owner_repository",
        table_name="workflow_pack_registrations",
    )
    op.drop_index(
        "ix_workflow_pack_registrations_pack_family",
        table_name="workflow_pack_registrations",
    )
    op.drop_table("workflow_pack_registrations")
