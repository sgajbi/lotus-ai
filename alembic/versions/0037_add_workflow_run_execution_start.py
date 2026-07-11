"""add workflow run execution start

Revision ID: 0037_add_workflow_run_execution_start
Revises: 0036_add_workflow_run_attestation_source
"""

from alembic import op
import sqlalchemy as sa


revision = "0037_add_workflow_run_execution_start"
down_revision = "0036_add_workflow_run_attestation_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workflow_pack_runs",
        sa.Column(
            "execution_started_at",
            sa.String(64),
            nullable=False,
            server_default="unverifiable",
        ),
    )


def downgrade() -> None:
    op.drop_column("workflow_pack_runs", "execution_started_at")
