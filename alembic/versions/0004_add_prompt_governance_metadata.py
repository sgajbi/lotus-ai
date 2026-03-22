from __future__ import annotations

from alembic import context
from alembic import op
import sqlalchemy as sa


revision = "0004_add_prompt_governance_metadata"
down_revision = "0003_create_prompt_definitions_table"
branch_labels = None
depends_on = None


def _prompt_definitions_table(include_governance_columns: bool) -> sa.Table:
    columns: list[sa.Column[object]] = [
        sa.Column("task_id", sa.String(length=128), primary_key=True, nullable=False),
        sa.Column("prompt_version", sa.String(length=128), nullable=False),
        sa.Column("prompt_kind", sa.String(length=64), nullable=False),
        sa.Column("system_instructions", sa.Text(), nullable=False),
        sa.Column("output_contract_notes", sa.Text(), nullable=False),
    ]
    if include_governance_columns:
        columns.extend(
            [
                sa.Column("lifecycle_status", sa.String(length=32), nullable=False),
                sa.Column("management_mode", sa.String(length=32), nullable=False),
                sa.Column("source_reference", sa.Text(), nullable=False),
            ]
        )
    return sa.Table("prompt_definitions", sa.MetaData(), *columns)


def upgrade() -> None:
    batch_kwargs = {}
    if context.is_offline_mode():
        batch_kwargs["copy_from"] = _prompt_definitions_table(include_governance_columns=False)
    with op.batch_alter_table("prompt_definitions", **batch_kwargs) as batch_op:
        batch_op.add_column(sa.Column("lifecycle_status", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("management_mode", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("source_reference", sa.Text(), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE prompt_definitions
            SET lifecycle_status = 'ACTIVE',
                management_mode = 'MIGRATION_MANAGED',
                source_reference = 'alembic:0003_create_prompt_definitions_table'
            """
        )
    )

    batch_kwargs = {}
    if context.is_offline_mode():
        batch_kwargs["copy_from"] = _prompt_definitions_table(include_governance_columns=True)
    with op.batch_alter_table("prompt_definitions", **batch_kwargs) as batch_op:
        batch_op.alter_column("lifecycle_status", nullable=False)
        batch_op.alter_column("management_mode", nullable=False)
        batch_op.alter_column("source_reference", nullable=False)


def downgrade() -> None:
    batch_kwargs = {}
    if context.is_offline_mode():
        batch_kwargs["copy_from"] = _prompt_definitions_table(include_governance_columns=True)
    with op.batch_alter_table("prompt_definitions", **batch_kwargs) as batch_op:
        batch_op.drop_column("source_reference")
        batch_op.drop_column("management_mode")
        batch_op.drop_column("lifecycle_status")
