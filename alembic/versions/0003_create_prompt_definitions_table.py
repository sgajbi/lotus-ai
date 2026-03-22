from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_create_prompt_definitions_table"
down_revision = "0002_create_retrieval_metadata_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prompt_definitions",
        sa.Column("task_id", sa.String(length=128), primary_key=True, nullable=False),
        sa.Column("prompt_version", sa.String(length=128), nullable=False),
        sa.Column("prompt_kind", sa.String(length=64), nullable=False),
        sa.Column("system_instructions", sa.Text(), nullable=False),
        sa.Column("output_contract_notes", sa.Text(), nullable=False),
    )

    prompt_table = sa.table(
        "prompt_definitions",
        sa.column("task_id", sa.String()),
        sa.column("prompt_version", sa.String()),
        sa.column("prompt_kind", sa.String()),
        sa.column("system_instructions", sa.Text()),
        sa.column("output_contract_notes", sa.Text()),
    )

    op.bulk_insert(
        prompt_table,
        [
            {
                "task_id": "explain.v1",
                "prompt_version": "foundation.explain.v1",
                "prompt_kind": "system",
                "system_instructions": (
                    "Explain structured Lotus domain outputs clearly, conservatively, and without "
                    "inventing missing business facts."
                ),
                "output_contract_notes": (
                    "Output must remain explanation-oriented, enterprise-safe, and non-authoritative."
                ),
            },
            {
                "task_id": "summarize.v1",
                "prompt_version": "foundation.summarize.v1",
                "prompt_kind": "system",
                "system_instructions": (
                    "Summarize caller-provided structured inputs into concise, decision-supporting text."
                ),
                "output_contract_notes": "Output is a draft summary, not business truth.",
            },
            {
                "task_id": "classify.v1",
                "prompt_version": "foundation.classify.v1",
                "prompt_kind": "system",
                "system_instructions": (
                    "Classify caller-provided structured content into bounded categories only."
                ),
                "output_contract_notes": "Classification must remain within caller-approved label sets.",
            },
            {
                "task_id": "extract.v1",
                "prompt_version": "foundation.extract.v1",
                "prompt_kind": "system",
                "system_instructions": "Extract structured fields from curated caller content.",
                "output_contract_notes": "Extraction output must stay schema-bound and conservative.",
            },
            {
                "task_id": "generate_structured.v1",
                "prompt_version": "foundation.generate_structured.v1",
                "prompt_kind": "system",
                "system_instructions": "Generate schema-bound structured output from curated caller context.",
                "output_contract_notes": "Generated output must remain draft-only and schema-bound.",
            },
            {
                "task_id": "knowledge_search.v1",
                "prompt_version": "foundation.knowledge_search.v1",
                "prompt_kind": "system",
                "system_instructions": "Search approved Lotus knowledge sources with traceable provenance.",
                "output_contract_notes": "Citations and source attribution are mandatory when enabled.",
            },
            {
                "task_id": "knowledge_answer.v1",
                "prompt_version": "foundation.knowledge_answer.v1",
                "prompt_kind": "system",
                "system_instructions": (
                    "Answer questions from approved Lotus knowledge sources with explicit citations."
                ),
                "output_contract_notes": "Refuse when sources are insufficient or unsupported.",
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("prompt_definitions")
