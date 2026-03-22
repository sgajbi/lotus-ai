"""add retrieval document promotion status

Revision ID: 0009_add_retrieval_document_promotion_status
Revises: 0008_enable_catalog_only_retrieval_sources
Create Date: 2026-03-22 22:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0009_add_retrieval_document_promotion_status"
down_revision = "0008_enable_catalog_only_retrieval_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "retrieval_documents",
        sa.Column(
            "promotion_status",
            sa.String(length=64),
            nullable=False,
            server_default="STAGED",
        ),
    )

    op.execute(
        """
        UPDATE retrieval_documents
        SET promotion_status = CASE
            WHEN source_id IN ('lotus-platform-rfcs', 'lotus-ai-architecture')
                THEN 'SEARCHABLE'
            ELSE 'STAGED'
        END
        """
    )


def downgrade() -> None:
    op.drop_column("retrieval_documents", "promotion_status")
