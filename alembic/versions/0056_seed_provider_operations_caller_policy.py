"""seed lotus-ai-provider-operations caller policy

Revision ID: 0056_seed_provider_operations_caller_policy
Revises: 0055_add_workflow_pack_admission_leases
Create Date: 2026-08-31

Issue #149 S2: every protected route now requires a registered ACTIVE
caller. The provider-operations recorder identity posts retention and
deletion confirmations over HTTP and therefore needs its own policy row;
it grants no task, retrieval, or control capability.
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0056_seed_provider_operations_caller_policy"
down_revision = "0055_add_workflow_pack_admission_leases"
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
            'lotus-ai-provider-operations',
            'ACTIVE',
            'Internal provider-operations recorder identity for retention and deletion confirmations; grants no task, retrieval, or control capability.',
            '[]',
            '[]',
            FALSE,
            FALSE,
            FALSE,
            FALSE,
            'OPTIONAL',
            '[]',
            '2026-08-31T00:00:00Z'
        )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM caller_policies WHERE caller_app = 'lotus-ai-provider-operations'")
