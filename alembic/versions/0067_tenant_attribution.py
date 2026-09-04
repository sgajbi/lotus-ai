"""tenant attribution for async jobs and artifacts

Revision ID: 0067_tenant_attribution
Revises: 0066_provider_attempt_debits
Create Date: 2026-09-04

Issue #291: client-derived durable content carries source-owned tenant
attribution at creation time wherever tenant erasure is a required
obligation. Columns are nullable on purpose: historical rows have no
source-owned attribution, stay NULL, and are never guessed - they erase by
the families' existing time-bounded expiry only.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0067_tenant_attribution"
down_revision = "0066_provider_attempt_debits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("async_jobs", sa.Column("tenant_id", sa.String(length=128), nullable=True))
    op.create_index("ix_async_jobs_tenant_id", "async_jobs", ["tenant_id"])
    op.add_column("artifact_metadata", sa.Column("tenant_id", sa.String(length=128), nullable=True))
    op.create_index("ix_artifact_metadata_tenant_id", "artifact_metadata", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_artifact_metadata_tenant_id", table_name="artifact_metadata")
    op.drop_column("artifact_metadata", "tenant_id")
    op.drop_index("ix_async_jobs_tenant_id", table_name="async_jobs")
    op.drop_column("async_jobs", "tenant_id")
