"""add audit access denial reason

Revision ID: 0058_add_audit_access_denial_reason
Revises: 0057_add_audit_output_validation
Create Date: 2026-09-01

Issue #167 S1: a refused privileged audit read is now recorded, with the
reason it was refused. Nullable: SUCCEEDED and NOT_FOUND events carry no
denial reason, and every event written before this slice was one of those -
a refusal left no row at all, which is the defect being closed.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0058_add_audit_access_denial_reason"
down_revision = "0057_add_audit_output_validation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audit_access_events",
        sa.Column("denial_reason", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("audit_access_events", "denial_reason")
