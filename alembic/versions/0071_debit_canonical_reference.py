"""debit canonical reference

Revision ID: 0071_debit_canonical_reference
Revises: 0070_candidate_identity_v2
Create Date: 2026-09-05

Issue #314: new attempt-debit rows additionally bind the canonical
candidate identity. The debit_id keeps its v1-shaped idempotency identity
forever - historical economic evidence is never rewritten - and historical
rows keep this column honestly null.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0071_debit_canonical_reference"
down_revision = "0070_candidate_identity_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "provider_attempt_debits",
        sa.Column("candidate_id_v2", sa.String(length=80), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("provider_attempt_debits", "candidate_id_v2")
