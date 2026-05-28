"""allow lotus-advise Singapore tenant workflow-pack execution

Revision ID: 0033_allow_lotus_advise_sg_tenant
Revises: 0032_add_workflow_pack_queue_event_tables
Create Date: 2026-05-28
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0033_allow_lotus_advise_sg_tenant"
down_revision = "0032_add_workflow_pack_queue_event_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE caller_policies
        SET
            restricted_tenant_ids = '["tenant-us-002","tenant-sg-001"]',
            description = 'Advisory application integration with bounded task access for governed advisory workflow-pack execution.',
            updated_at = '2026-05-28T00:00:00Z'
        WHERE caller_app = 'lotus-advise'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE caller_policies
        SET
            restricted_tenant_ids = '["tenant-us-002"]',
            description = 'Advisory application integration with bounded task access.',
            updated_at = '2026-03-24T00:00:00Z'
        WHERE caller_app = 'lotus-advise'
        """
    )
