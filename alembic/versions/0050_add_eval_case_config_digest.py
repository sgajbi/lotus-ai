"""add provider config digest to evaluation case results

Revision ID: 0050_add_eval_case_config_digest
Revises: 0049_add_reproducibility_identity
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0050_add_eval_case_config_digest"
down_revision = "0049_add_reproducibility_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "evaluation_case_results",
        sa.Column("provider_config_sha256", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("evaluation_case_results", "provider_config_sha256")
