"""add drain/hard-kill semantics to kill-switch activations

Revision ID: 0051_add_kill_switch_semantics
Revises: 0050_add_eval_case_config_digest
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0051_add_kill_switch_semantics"
down_revision = "0050_add_eval_case_config_digest"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "kill_switch_activations",
        sa.Column(
            "semantics",
            sa.String(length=16),
            nullable=False,
            server_default="HARD_KILL",
        ),
    )


def downgrade() -> None:
    op.drop_column("kill_switch_activations", "semantics")
