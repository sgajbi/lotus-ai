"""candidate debit identity

Revision ID: 0069_candidate_debit_identity
Revises: 0068_serving_policy_versions
Create Date: 2026-09-04

Issue #299: the attempt debit identity uses the full serving candidate
(the catalogue entry id binding provider, model revision and deployment),
because two model candidates at the same provider are normal serving
topology and a provider id would collide their debits. The row persists
the serving identity so a later audit can answer which catalogue entry,
provider, model revision, rate card and attempt each debit describes.
Rows recorded before this migration keep null candidate columns - their
debit_id carries only the provider id, honestly.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0069_candidate_debit_identity"
down_revision = "0068_serving_policy_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "provider_attempt_debits",
        sa.Column("candidate_entry_id", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "provider_attempt_debits",
        sa.Column("model_revision", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "provider_attempt_debits",
        sa.Column("attempt_index", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("provider_attempt_debits", "attempt_index")
    op.drop_column("provider_attempt_debits", "model_revision")
    op.drop_column("provider_attempt_debits", "candidate_entry_id")
