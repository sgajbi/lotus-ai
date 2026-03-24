"""add audit prompt selection payload

Revision ID: 0018_add_audit_prompt_selection_payload
Revises: 0017_seed_prompt_rollout_candidates
Create Date: 2026-03-23 01:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018_add_audit_prompt_selection_payload"
down_revision = "0017_seed_prompt_rollout_candidates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_records", sa.Column("prompt_selection_payload", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_records", "prompt_selection_payload")
