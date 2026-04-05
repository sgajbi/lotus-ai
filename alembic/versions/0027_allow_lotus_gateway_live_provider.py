"""allow lotus-gateway live provider execution

Revision ID: 0027_allow_lotus_gateway_live_provider
Revises: 0026_seed_lotus_gateway_caller_policy
Create Date: 2026-04-04
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0027_allow_lotus_gateway_live_provider"
down_revision = "0026_seed_lotus_gateway_caller_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE caller_policies
        SET
            allow_live_provider = TRUE,
            description = 'Gateway BFF caller for source-bounded advisor brief generation over pre-assembled portfolio and performance facts. Live explain.v1 execution is allowed when provider rollout and task allowlists are enabled.',
            updated_at = '2026-04-04T00:00:00Z'
        WHERE caller_app = 'lotus-gateway'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE caller_policies
        SET
            allow_live_provider = FALSE,
            description = 'Gateway BFF caller for source-bounded advisor brief generation over pre-assembled portfolio and performance facts.',
            updated_at = '2026-04-04T00:00:00Z'
        WHERE caller_app = 'lotus-gateway'
        """
    )
