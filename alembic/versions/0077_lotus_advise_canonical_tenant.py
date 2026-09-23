"""Admit the canonical tenant for lotus-advise workflow execution.

The canonical front-office contract carries ``tenant-sg``.  The existing
lotus-advise policy admitted only the legacy proof identities, so supported
Advisory Copilot workflow-pack execution was refused before a run could be
recorded (issue #379).  The caller remains RESTRICTED and the existing
admissions remain intact.

Revision ID: 0077_lotus_advise_canonical_tenant
Revises: 0076_manifest_content_digest
"""

from alembic import op

revision = "0077_lotus_advise_canonical_tenant"
down_revision = "0076_manifest_content_digest"
branch_labels = None
depends_on = None

_ADMITTED = '["tenant-us-002","tenant-sg-001","tenant-sg"]'
_PRIOR = '["tenant-us-002","tenant-sg-001"]'


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE caller_policies
        SET restricted_tenant_ids = '{_ADMITTED}',
            updated_at = '2026-09-23T00:00:00Z'
        WHERE caller_app = 'lotus-advise'
          AND tenant_policy_mode = 'RESTRICTED'
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        UPDATE caller_policies
        SET restricted_tenant_ids = '{_PRIOR}',
            updated_at = '2026-05-28T00:00:00Z'
        WHERE caller_app = 'lotus-advise'
          AND tenant_policy_mode = 'RESTRICTED'
        """
    )
