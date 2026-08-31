"""add audit output validation columns

Revision ID: 0057_add_audit_output_validation
Revises: 0056_seed_provider_operations_caller_policy
Create Date: 2026-08-31

Issue #156 S1: every audit record carries the deterministic
output-validation verdict - the full outcome payload for evidence, and the
state alone as a queryable column. Nullable: records persisted before
validation existed, and runtime-failure records with no output, carry null.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0057_add_audit_output_validation"
down_revision = "0056_seed_provider_operations_caller_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audit_records",
        sa.Column("output_validation_payload", sa.JSON(), nullable=True),
    )
    op.add_column(
        "audit_records",
        sa.Column("validation_state", sa.String(length=40), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("audit_records", "validation_state")
    op.drop_column("audit_records", "output_validation_payload")
