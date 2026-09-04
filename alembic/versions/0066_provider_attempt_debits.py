"""provider attempt debits

Revision ID: 0066_provider_attempt_debits
Revises: 0065_data_lifecycle_evidence
Create Date: 2026-09-04

Issue #289: every potentially billable provider attempt becomes durable
economic evidence at the attempt boundary. The debit id is the idempotent
attempt identity, so a row exists exactly once per attempt regardless of
whether the execution later succeeds, fails completely, falls back, or the
process dies.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0066_provider_attempt_debits"
down_revision = "0065_data_lifecycle_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_attempt_debits",
        sa.Column("debit_id", sa.String(length=200), primary_key=True),
        sa.Column("provider_id", sa.String(length=128), nullable=False),
        sa.Column("basis", sa.String(length=32), nullable=False),
        sa.Column("amount_usd", sa.Float(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("rate_card_ref", sa.String(length=128), nullable=False),
        sa.Column("recorded_at", sa.String(length=64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("provider_attempt_debits")
