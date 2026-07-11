"""add workflow run model approval reference

Revision ID: 0038_add_workflow_run_model_approval_ref
Revises: 0037_add_workflow_run_execution_start
"""

from alembic import op
import sqlalchemy as sa


revision = "0038_add_workflow_run_model_approval_ref"
down_revision = "0037_add_workflow_run_execution_start"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workflow_pack_runs",
        sa.Column(
            "model_risk_approval_ref",
            sa.String(256),
            nullable=False,
            server_default="unverifiable",
        ),
    )


def downgrade() -> None:
    op.drop_column("workflow_pack_runs", "model_risk_approval_ref")
