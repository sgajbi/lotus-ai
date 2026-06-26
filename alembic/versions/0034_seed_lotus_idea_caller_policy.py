"""seed lotus-idea caller policy

Revision ID: 0034_seed_lotus_idea_caller_policy
Revises: 0033_allow_lotus_advise_sg_tenant
Create Date: 2026-06-26
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0034_seed_lotus_idea_caller_policy"
down_revision = "0033_allow_lotus_advise_sg_tenant"
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
            'lotus-idea',
            'ACTIVE',
            'Idea service caller for review-gated explanation generation over redacted opportunity evidence packets.',
            '["explain.v1"]',
            '[]',
            FALSE,
            FALSE,
            FALSE,
            FALSE,
            'RESTRICTED',
            '["tenant-sg-001"]',
            '2026-06-26T00:00:00Z'
        )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM caller_policies WHERE caller_app = 'lotus-idea'")
