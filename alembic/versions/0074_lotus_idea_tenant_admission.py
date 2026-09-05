"""Admit the canonical platform tenant for the lotus-idea caller.

Real Idea candidates carry the platform's canonical tenant
(`tenant-private-bank-sg`), but migration 0034 seeded the lotus-idea caller
policy restricted to the lotus-ai-local proof fixture tenant only, so the
first live idea-explanation journey execution was refused with
BLOCKED_TENANT_NOT_ALLOWED (issue #323). Tenant admission stays RESTRICTED;
only the admitted vocabulary aligns with platform truth. The proof fixture
tenant is retained so existing runtime-proof evidence stays valid.

Revision ID: 0074_lotus_idea_tenant_admission
Revises: 0073_capability_evidence_records
"""

from alembic import op

revision = "0074_lotus_idea_tenant_admission"
down_revision = "0073_capability_evidence_records"
branch_labels = None
depends_on = None

_ADMITTED = '["tenant-private-bank-sg", "tenant-sg-001"]'
_PRIOR = '["tenant-sg-001"]'


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE caller_policies
        SET restricted_tenant_ids = '{_ADMITTED}',
            updated_at = '2026-09-05T00:00:00Z'
        WHERE caller_app = 'lotus-idea'
          AND tenant_policy_mode = 'RESTRICTED'
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        UPDATE caller_policies
        SET restricted_tenant_ids = '{_PRIOR}',
            updated_at = '2026-06-26T00:00:00Z'
        WHERE caller_app = 'lotus-idea'
          AND tenant_policy_mode = 'RESTRICTED'
        """
    )
