"""Content-derived manifest identity on runs and capability evidence (issue #351).

Additive nullable columns: the evidence version guard compares the digest
(content truth) alongside the manifest_version label (operator intent) -
either mismatch refuses. Historical rows keep NULL and stay honored under
the label-only guard, stated rather than backfilled.

Revision ID: 0076_manifest_content_digest
Revises: 0075_governed_action_claim_evidence
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0076_manifest_content_digest"
down_revision = "0075_governed_action_claim_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "evaluation_runs",
        sa.Column("manifest_content_digest", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "capability_evidence_records",
        sa.Column("manifest_content_digest", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("capability_evidence_records", "manifest_content_digest")
    op.drop_column("evaluation_runs", "manifest_content_digest")
