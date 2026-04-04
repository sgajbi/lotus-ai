"""seed lotus-gateway caller policy

Revision ID: 0026_seed_lotus_gateway_caller_policy
Revises: 0025_add_retrieval_ingestion_state_tables
Create Date: 2026-04-04
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0026_seed_lotus_gateway_caller_policy"
down_revision = "0025_add_retrieval_ingestion_state_tables"
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
            'lotus-gateway',
            'ACTIVE',
            'Gateway BFF caller for source-bounded advisor brief generation over pre-assembled portfolio and performance facts.',
            '["explain.v1"]',
            '[]',
            0,
            0,
            0,
            0,
            'OPTIONAL',
            '[]',
            '2026-04-04T00:00:00Z'
        )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM caller_policies WHERE caller_app = 'lotus-gateway'")
