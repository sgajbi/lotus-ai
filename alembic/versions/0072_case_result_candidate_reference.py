"""case result candidate reference

Revision ID: 0072_case_result_candidate_reference
Revises: 0071_debit_canonical_reference
Create Date: 2026-09-05

Issue #312: evaluation case results capture the served candidate's
canonical identity so capability evidence can bind the exact candidate and
revision it proves. Historical rows stay honestly null - unknown serving
identity yields no evidence.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0072_case_result_candidate_reference"
down_revision = "0071_debit_canonical_reference"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "evaluation_case_results",
        sa.Column("candidate_id_v2", sa.String(length=80), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("evaluation_case_results", "candidate_id_v2")
