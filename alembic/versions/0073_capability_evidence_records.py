"""capability evidence records

Revision ID: 0073_capability_evidence_records
Revises: 0072_case_result_candidate_reference
Create Date: 2026-09-05

Issue #312: authoritative scope-aware observed-capability claims. One row
per declared proof per PASS run, bound to the exact canonical candidate,
revision, scope, fixture family, manifest version, run and provenance.
Eligibility consumes matching PASS rows; nothing is ever widened.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0073_capability_evidence_records"
down_revision = "0072_case_result_candidate_reference"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "capability_evidence_records",
        sa.Column("evidence_id", sa.String(length=160), primary_key=True),
        sa.Column("candidate_id_v2", sa.String(length=80), nullable=False, index=True),
        sa.Column("model_revision", sa.String(length=128), nullable=False),
        sa.Column("dimension", sa.String(length=64), nullable=False, index=True),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_key", sa.String(length=256), nullable=True),
        sa.Column("fixture_id", sa.String(length=128), nullable=False),
        sa.Column("manifest_version", sa.String(length=64), nullable=False),
        sa.Column("evaluation_run_id", sa.String(length=128), nullable=False, index=True),
        sa.Column("verdict", sa.String(length=16), nullable=False),
        sa.Column("triggered_by", sa.String(length=256), nullable=True),
        sa.Column("recorded_at", sa.String(length=64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("capability_evidence_records")
