"""enable catalog-only retrieval sources

Revision ID: 0008_enable_catalog_only_retrieval_sources
Revises: 0007_add_audit_caller_identity_fields
Create Date: 2026-03-22 00:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "0008_enable_catalog_only_retrieval_sources"
down_revision = "0007_add_audit_caller_identity_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE retrieval_sources
        SET enabled = 1
        WHERE source_id IN ('lotus-platform-rfcs', 'lotus-ai-architecture')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE retrieval_sources
        SET enabled = 0
        WHERE source_id IN ('lotus-platform-rfcs', 'lotus-ai-architecture')
        """
    )
