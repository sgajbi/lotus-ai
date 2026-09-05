"""Claim and result evidence on governed actions.

One approval session must atomically own a governed action's execution
(issue #327): the CLAIMED transition carries the approver evidence from the
instant of the claim, and the durable result payload makes evidence-bearing
responses (an erasure receipt) retrievable after a lost response without
re-executing the effect. Both columns are additive and nullable; existing
rows are untouched historical evidence.

Revision ID: 0075_governed_action_claim_evidence
Revises: 0074_lotus_idea_tenant_admission
"""

import sqlalchemy as sa
from alembic import op

revision = "0075_governed_action_claim_evidence"
down_revision = "0074_lotus_idea_tenant_admission"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "provider_governed_actions",
        sa.Column("claimed_at", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "provider_governed_actions",
        sa.Column("result_payload", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("provider_governed_actions", "result_payload")
    op.drop_column("provider_governed_actions", "claimed_at")
