"""seed lotus-performance caller policy

Revision ID: 0024_seed_lotus_performance_caller_policy
Revises: 0023_add_runtime_artifact_refs
Create Date: 2026-03-24
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0024_seed_lotus_performance_caller_policy"
down_revision = "0023_add_runtime_artifact_refs"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
        ) VALUES (
            'lotus-performance',
            'ACTIVE',
            'First-production-use-case integration for explanation-only analytics commentary.',
            '["explain.v1"]',
            '[]',
            0,
            0,
            0,
            0,
            'RESTRICTED',
            '["tenant-sg-001"]',
            '2026-03-24T12:00:00Z'
        )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM caller_policies WHERE caller_app = 'lotus-performance'")
