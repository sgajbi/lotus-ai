"""add caller policy tables

Revision ID: 0019_add_caller_policy_tables
Revises: 0018_add_audit_prompt_selection_payload
Create Date: 2026-03-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0019_add_caller_policy_tables"
down_revision = "0018_add_audit_prompt_selection_payload"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "caller_policies",
        sa.Column("caller_app", sa.String(length=128), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("allowed_task_ids", sa.JSON(), nullable=False),
        sa.Column("allowed_retrieval_source_ids", sa.JSON(), nullable=False),
        sa.Column("allow_live_provider", sa.Boolean(), nullable=False),
        sa.Column("allow_async_control", sa.Boolean(), nullable=False),
        sa.Column("allow_prompt_control", sa.Boolean(), nullable=False),
        sa.Column("allow_provider_control", sa.Boolean(), nullable=False),
        sa.Column("tenant_policy_mode", sa.String(length=32), nullable=False),
        sa.Column("restricted_tenant_ids", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("caller_app"),
    )
    op.create_index(
        "ix_caller_policies_updated_at", "caller_policies", ["updated_at"], unique=False
    )

    op.execute(
        """
        INSERT INTO caller_policies (
            caller_app,
            lifecycle_status,
            description,
            allowed_task_ids,
            allowed_retrieval_source_ids,
            allow_live_provider,
            allow_async_control,
            allow_prompt_control,
            allow_provider_control,
            tenant_policy_mode,
            restricted_tenant_ids,
            updated_at
        ) VALUES
        (
            'lotus-manage',
            'ACTIVE',
            'Primary managed-app integration for bounded task execution.',
            '["explain.v1","summarize.v1","generate_structured.v1","knowledge_search.v1","knowledge_answer.v1"]',
            '["lotus-platform-rfcs","lotus-ai-architecture"]',
            TRUE,
            FALSE,
            FALSE,
            FALSE,
            'RESTRICTED',
            '["tenant-sg-001"]',
            '2026-03-24T00:00:00Z'
        ),
        (
            'lotus-advise',
            'ACTIVE',
            'Advisory application integration with bounded task access.',
            '["explain.v1","summarize.v1","knowledge_answer.v1"]',
            '["lotus-platform-rfcs"]',
            FALSE,
            FALSE,
            FALSE,
            FALSE,
            'RESTRICTED',
            '["tenant-us-002"]',
            '2026-03-24T00:00:00Z'
        ),
        (
            'lotus-platform',
            'ACTIVE',
            'Platform operator and automation caller for governed control planes.',
            '[]',
            '[]',
            FALSE,
            TRUE,
            TRUE,
            TRUE,
            'OPTIONAL',
            '[]',
            '2026-03-24T00:00:00Z'
        ),
        (
            'lotus-workbench',
            'ACTIVE',
            'Workbench caller for bounded retrieval exploration.',
            '["knowledge_search.v1","knowledge_answer.v1"]',
            '["lotus-platform-rfcs","lotus-ai-architecture"]',
            FALSE,
            FALSE,
            FALSE,
            FALSE,
            'OPTIONAL',
            '[]',
            '2026-03-24T00:00:00Z'
        )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_caller_policies_updated_at", table_name="caller_policies")
    op.drop_table("caller_policies")
