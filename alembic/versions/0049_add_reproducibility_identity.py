"""add reproducibility identity: prompt hashes, sampling, config digests

Revision ID: 0049_add_reproducibility_identity
Revises: 0048_add_rate_cards
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0049_add_reproducibility_identity"
down_revision = "0048_add_rate_cards"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audit_records", sa.Column("prompt_content_sha256", sa.String(length=64), nullable=True)
    )
    op.add_column("audit_records", sa.Column("sampling_payload", sa.JSON(), nullable=True))
    op.add_column(
        "audit_records", sa.Column("provider_config_sha256", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "prompt_definition_versions",
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "workflow_pack_runs",
        sa.Column("provider_config_sha256", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workflow_pack_runs", "provider_config_sha256")
    op.drop_column("prompt_definition_versions", "content_sha256")
    op.drop_column("audit_records", "provider_config_sha256")
    op.drop_column("audit_records", "sampling_payload")
    op.drop_column("audit_records", "prompt_content_sha256")
