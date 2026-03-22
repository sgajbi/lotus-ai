from __future__ import annotations

from alembic import context
from alembic import op
import sqlalchemy as sa


revision = "0005_add_audit_safety_metadata"
down_revision = "0004_add_prompt_governance_metadata"
branch_labels = None
depends_on = None


def _audit_records_table(include_safety_columns: bool) -> sa.Table:
    columns: list[sa.Column[object]] = [
        sa.Column("request_id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("task_id", sa.String(length=128), nullable=False),
        sa.Column("caller_app", sa.String(length=128), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=128), nullable=False),
        sa.Column("provider_mode", sa.String(length=64), nullable=False),
    ]
    if include_safety_columns:
        columns.extend(
            [
                sa.Column("safety_mode", sa.String(length=64), nullable=False),
                sa.Column("redaction_posture", sa.String(length=64), nullable=False),
                sa.Column("enforced_safety_controls", sa.JSON(), nullable=False),
            ]
        )
    columns.extend(
        [
            sa.Column("generated_at", sa.String(length=64), nullable=False),
            sa.Column("stubbed", sa.Boolean(), nullable=False),
            sa.Column("context_summary", sa.Text(), nullable=False),
            sa.Column("context_keys", sa.JSON(), nullable=False),
            sa.Column("source_refs", sa.JSON(), nullable=False),
            sa.Column("result_preview", sa.Text(), nullable=False),
            sa.Column("structured_output", sa.JSON(), nullable=False),
        ]
    )
    return sa.Table("audit_records", sa.MetaData(), *columns)


def upgrade() -> None:
    batch_kwargs = {}
    if context.is_offline_mode():
        batch_kwargs["copy_from"] = _audit_records_table(include_safety_columns=False)
    with op.batch_alter_table("audit_records", **batch_kwargs) as batch_op:
        batch_op.add_column(sa.Column("safety_mode", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("redaction_posture", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("enforced_safety_controls", sa.JSON(), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE audit_records
            SET safety_mode = 'documented_only',
                redaction_posture = 'DOCUMENTED_ONLY',
                enforced_safety_controls = '["response_labeling","correlation_and_audit"]'
            """
        )
    )

    batch_kwargs = {}
    if context.is_offline_mode():
        batch_kwargs["copy_from"] = _audit_records_table(include_safety_columns=True)
    with op.batch_alter_table("audit_records", **batch_kwargs) as batch_op:
        batch_op.alter_column("safety_mode", nullable=False)
        batch_op.alter_column("redaction_posture", nullable=False)
        batch_op.alter_column("enforced_safety_controls", nullable=False)


def downgrade() -> None:
    batch_kwargs = {}
    if context.is_offline_mode():
        batch_kwargs["copy_from"] = _audit_records_table(include_safety_columns=True)
    with op.batch_alter_table("audit_records", **batch_kwargs) as batch_op:
        batch_op.drop_column("enforced_safety_controls")
        batch_op.drop_column("redaction_posture")
        batch_op.drop_column("safety_mode")
