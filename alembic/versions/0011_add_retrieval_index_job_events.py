"""add retrieval index job events

Revision ID: 0011_add_retrieval_index_job_events
Revises: 0010_add_retrieval_chunk_embedding_schema
Create Date: 2026-03-22 23:40:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0011_add_retrieval_index_job_events"
down_revision = "0010_add_retrieval_chunk_embedding_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "retrieval_index_job_events",
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.String(length=128), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("recorded_at", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["retrieval_index_jobs.job_id"]),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_retrieval_index_job_events_job_id",
        "retrieval_index_job_events",
        ["job_id"],
    )

    op.execute(
        """
        INSERT INTO retrieval_index_job_events (event_id, job_id, stage, status, recorded_at, notes)
        VALUES
            (
                'evt_retjob_lotus_platform_rfcs_source_curation',
                'retjob_lotus_platform_rfcs',
                'STAGED',
                'COMPLETED',
                '2026-03-22T08:00:00Z',
                'Approved RFC source inventory and promoted documents are ready for deterministic indexing.'
            ),
            (
                'evt_retjob_lotus_platform_rfcs_document_inventory',
                'retjob_lotus_platform_rfcs',
                'STAGED',
                'COMPLETED',
                '2026-03-22T08:01:00Z',
                'Document inventory and chunk checksums were recorded for replayable indexing.'
            ),
            (
                'evt_retjob_lotus_platform_rfcs_embedding_generation',
                'retjob_lotus_platform_rfcs',
                'STAGED',
                'STAGED',
                '2026-03-22T08:02:00Z',
                'Embedding records are staged in persistence, but live generation remains disabled.'
            ),
            (
                'evt_retjob_lotus_platform_rfcs_vector_persistence',
                'retjob_lotus_platform_rfcs',
                'DOCUMENTED',
                'STAGED',
                '2026-03-22T08:03:00Z',
                'Vector persistence contract is defined for PostgreSQL with pgvector pending live rollout.'
            ),
            (
                'evt_retjob_lotus_platform_standards_source_curation',
                'retjob_lotus_platform_standards',
                'STAGED',
                'COMPLETED',
                '2026-03-22T08:10:00Z',
                'Standards source inventory is approved and staged for indexing.'
            ),
            (
                'evt_retjob_lotus_platform_standards_document_inventory',
                'retjob_lotus_platform_standards',
                'STAGED',
                'FAILED',
                '2026-03-22T08:11:00Z',
                'Indexing is blocked because staged standards documents are not yet promoted into searchable scope.'
            ),
            (
                'evt_retjob_lotus_ai_architecture_source_curation',
                'retjob_lotus_ai_architecture',
                'STAGED',
                'COMPLETED',
                '2026-03-22T08:20:00Z',
                'Architecture source inventory and promoted documents are ready for deterministic indexing.'
            ),
            (
                'evt_retjob_lotus_ai_architecture_document_inventory',
                'retjob_lotus_ai_architecture',
                'STAGED',
                'COMPLETED',
                '2026-03-22T08:21:00Z',
                'Document inventory and chunk checksums were recorded for replayable indexing.'
            ),
            (
                'evt_retjob_lotus_ai_architecture_embedding_generation',
                'retjob_lotus_ai_architecture',
                'STAGED',
                'STAGED',
                '2026-03-22T08:22:00Z',
                'Embedding records are staged in persistence, but live generation remains disabled.'
            ),
            (
                'evt_retjob_lotus_openapi_derived_source_curation',
                'retjob_lotus_openapi_derived',
                'STAGED',
                'FAILED',
                '2026-03-22T08:30:00Z',
                'No promoted documents are available yet for this source, so indexing cannot proceed.'
            )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_retrieval_index_job_events_job_id", table_name="retrieval_index_job_events")
    op.drop_table("retrieval_index_job_events")
