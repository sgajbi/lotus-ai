"""add workflow run attestation source

Revision ID: 0036_add_workflow_run_attestation_source
Revises: 0035_add_workflow_pack_run_recovery_lineage
"""

from alembic import op
import sqlalchemy as sa


revision = "0036_add_workflow_run_attestation_source"
down_revision = "0035_add_workflow_pack_run_recovery_lineage"
branch_labels = None
depends_on = None


FIELDS = (
    ("evaluator_id", 128),
    ("evaluator_policy_version", 64),
    ("provider_id", 128),
    ("model_id", 128),
    ("model_version", 64),
    ("model_risk_status", 64),
    ("input_evidence_sha256", 64),
    ("output_content_sha256", 64),
    ("replay_nonce", 64),
)


def upgrade() -> None:
    for name, length in FIELDS:
        op.add_column(
            "workflow_pack_runs",
            sa.Column(name, sa.String(length), nullable=False, server_default="unverifiable"),
        )
    op.create_index(
        "ix_workflow_pack_runs_replay_nonce", "workflow_pack_runs", ["replay_nonce"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_pack_runs_replay_nonce", table_name="workflow_pack_runs")
    for name, _ in reversed(FIELDS):
        op.drop_column("workflow_pack_runs", name)
