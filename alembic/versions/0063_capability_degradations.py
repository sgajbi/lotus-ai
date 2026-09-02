"""capability degradations

Revision ID: 0063_capability_degradations
Revises: 0062_governed_model_promotion
Create Date: 2026-09-03

Issue #245, slice 2: an observed regression scoped to one capability
dimension degrades exactly that capability - immediately, under one verified
principal - without rewriting the entry's other evidence. Active
degradations live on the entry; cleared ones are pinned inside their
governed restore records.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0063_capability_degradations"
down_revision = "0062_governed_model_promotion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "model_catalogue_entries",
        sa.Column("capability_degradations", sa.JSON(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("model_catalogue_entries", "capability_degradations")
