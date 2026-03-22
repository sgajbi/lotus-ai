from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_create_audit_records_table"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_records",
        sa.Column("request_id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("task_id", sa.String(length=128), nullable=False),
        sa.Column("caller_app", sa.String(length=128), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=128), nullable=False),
        sa.Column("provider_mode", sa.String(length=64), nullable=False),
        sa.Column("generated_at", sa.String(length=64), nullable=False),
        sa.Column("stubbed", sa.Boolean(), nullable=False),
        sa.Column("context_summary", sa.Text(), nullable=False),
        sa.Column("context_keys", sa.JSON(), nullable=False),
        sa.Column("source_refs", sa.JSON(), nullable=False),
        sa.Column("result_preview", sa.Text(), nullable=False),
        sa.Column("structured_output", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_records")
