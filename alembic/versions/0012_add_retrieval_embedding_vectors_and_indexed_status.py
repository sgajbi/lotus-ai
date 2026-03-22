"""add retrieval embedding vectors and indexed status

Revision ID: 0012_add_retrieval_embedding_vectors_and_indexed_status
Revises: 0011_add_retrieval_index_job_events
Create Date: 2026-03-22 23:55:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0012_add_retrieval_embedding_vectors_and_indexed_status"
down_revision = "0011_add_retrieval_index_job_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "retrieval_chunk_embeddings",
        sa.Column("embedding_vector", sa.JSON(), nullable=False, server_default="[]"),
    )

    op.execute(
        """
        UPDATE retrieval_chunk_embeddings
        SET vector_dimensions = 16,
            embedding_vector = CASE embedding_id
                WHEN 'emb_chunk_rfc_0068_0001' THEN '[0.0, 0.0, 0.0, 0.142857, 0.428571, 0.0, 0.0, 0.0, 0.285714, 0.142857, 0.0, 0.428571, 0.0, 0.0, 0.571429, 0.428571]'
                WHEN 'emb_chunk_rfc_0069_0001' THEN '[0.0, 0.0, 0.601929, 0.361158, 0.0, 0.0, 0.361158, 0.0, 0.481543, 0.120386, 0.0, 0.120386, 0.0, 0.0, 0.240772, 0.240772]'
                WHEN 'emb_chunk_system_overview_0001' THEN '[0.0, 0.188982, 0.566947, 0.566947, 0.0, 0.0, 0.377964, 0.0, 0.188982, 0.188982, 0.0, 0.0, 0.0, 0.188982, 0.188982, 0.188982]'
                WHEN 'emb_chunk_retrieval_guide_0001' THEN '[0.0, 0.0, 0.312348, 0.624695, 0.156174, 0.0, 0.156174, 0.312348, 0.312348, 0.312348, 0.0, 0.312348, 0.0, 0.156174, 0.156174, 0.156174]'
                ELSE '[]'
            END
        """
    )

    op.execute(
        """
        UPDATE retrieval_documents
        SET index_status = 'INDEXED'
        WHERE promotion_status = 'SEARCHABLE'
        """
    )

    op.execute(
        """
        UPDATE retrieval_chunks
        SET index_status = 'INDEXED'
        WHERE document_id IN (
            SELECT document_id
            FROM retrieval_documents
            WHERE promotion_status = 'SEARCHABLE'
        )
        """
    )

    op.execute(
        """
        UPDATE retrieval_chunk_embeddings
        SET embedding_status = 'PERSISTED'
        WHERE document_id IN (
            SELECT document_id
            FROM retrieval_documents
            WHERE promotion_status = 'SEARCHABLE'
        )
        """
    )

    op.execute(
        """
        UPDATE retrieval_index_jobs
        SET status = CASE source_id
                WHEN 'lotus-platform-rfcs' THEN 'COMPLETED'
                WHEN 'lotus-ai-architecture' THEN 'COMPLETED'
                ELSE status
            END,
            message = CASE source_id
                WHEN 'lotus-platform-rfcs' THEN 'Promoted RFC documents have persisted embeddings and are ready for bounded indexed retrieval.'
                WHEN 'lotus-ai-architecture' THEN 'Promoted architecture documents have persisted embeddings and are ready for bounded indexed retrieval.'
                ELSE message
            END
        """
    )

    op.execute(
        """
        UPDATE retrieval_index_job_events
        SET status = 'COMPLETED',
            notes = CASE event_id
                WHEN 'evt_retjob_lotus_platform_rfcs_embedding_generation' THEN 'Persisted preview embeddings are available for promoted RFC chunks and can back bounded indexed retrieval.'
                WHEN 'evt_retjob_lotus_ai_architecture_embedding_generation' THEN 'Persisted preview embeddings are available for promoted architecture chunks and can back bounded indexed retrieval.'
                ELSE notes
            END
        WHERE event_id IN (
            'evt_retjob_lotus_platform_rfcs_embedding_generation',
            'evt_retjob_lotus_ai_architecture_embedding_generation'
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE retrieval_index_job_events
        SET status = 'STAGED',
            notes = CASE event_id
                WHEN 'evt_retjob_lotus_platform_rfcs_embedding_generation' THEN 'Embedding records are staged in persistence, but live generation remains disabled.'
                WHEN 'evt_retjob_lotus_ai_architecture_embedding_generation' THEN 'Embedding records are staged in persistence, but live generation remains disabled.'
                ELSE notes
            END
        WHERE event_id IN (
            'evt_retjob_lotus_platform_rfcs_embedding_generation',
            'evt_retjob_lotus_ai_architecture_embedding_generation'
        )
        """
    )

    op.execute(
        """
        UPDATE retrieval_index_jobs
        SET status = CASE source_id
                WHEN 'lotus-platform-rfcs' THEN 'STAGED'
                WHEN 'lotus-ai-architecture' THEN 'STAGED'
                ELSE status
            END,
            message = CASE source_id
                WHEN 'lotus-platform-rfcs' THEN 'Documents are staged for indexing, but vector indexing is not enabled yet.'
                WHEN 'lotus-ai-architecture' THEN 'Documents are staged for indexing, but vector indexing is not enabled yet.'
                ELSE message
            END
        """
    )

    op.execute(
        """
        UPDATE retrieval_chunk_embeddings
        SET embedding_status = 'STAGED',
            vector_dimensions = 1536
        """
    )

    op.execute(
        """
        UPDATE retrieval_chunks
        SET index_status = 'STAGED'
        WHERE document_id IN (
            SELECT document_id
            FROM retrieval_documents
            WHERE promotion_status = 'SEARCHABLE'
        )
        """
    )

    op.execute(
        """
        UPDATE retrieval_documents
        SET index_status = 'STAGED'
        WHERE promotion_status = 'SEARCHABLE'
        """
    )

    op.drop_column("retrieval_chunk_embeddings", "embedding_vector")
