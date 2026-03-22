"""add retrieval chunk embedding schema

Revision ID: 0010_add_retrieval_chunk_embedding_schema
Revises: 0009_add_retrieval_document_promotion_status
Create Date: 2026-03-22 23:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010_add_retrieval_chunk_embedding_schema"
down_revision = "0009_add_retrieval_document_promotion_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "retrieval_chunks",
        sa.Column(
            "content_checksum",
            sa.String(length=128),
            nullable=False,
            server_default="foundation-unset-checksum",
        ),
    )

    op.execute(
        """
        UPDATE retrieval_chunks
        SET content_checksum = CASE chunk_id
            WHEN 'chunk_rfc_0068_0001' THEN 'sha256:chunk-rfc-0068-0001'
            WHEN 'chunk_rfc_0069_0001' THEN 'sha256:chunk-rfc-0069-0001'
            WHEN 'chunk_obs_0001' THEN 'sha256:chunk-obs-0001'
            WHEN 'chunk_system_overview_0001' THEN 'sha256:chunk-system-overview-0001'
            WHEN 'chunk_retrieval_guide_0001' THEN 'sha256:chunk-retrieval-guide-0001'
            ELSE 'sha256:foundation-unset-checksum'
        END
        """
    )

    op.create_table(
        "retrieval_chunk_embeddings",
        sa.Column("embedding_id", sa.String(length=128), nullable=False),
        sa.Column("chunk_id", sa.String(length=128), nullable=False),
        sa.Column("document_id", sa.String(length=128), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("embedding_model", sa.String(length=128), nullable=False),
        sa.Column("embedding_status", sa.String(length=64), nullable=False),
        sa.Column("vector_dimensions", sa.Integer(), nullable=False),
        sa.Column("content_checksum", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["retrieval_chunks.chunk_id"]),
        sa.ForeignKeyConstraint(["document_id"], ["retrieval_documents.document_id"]),
        sa.ForeignKeyConstraint(["source_id"], ["retrieval_sources.source_id"]),
        sa.PrimaryKeyConstraint("embedding_id"),
    )
    op.create_index(
        "ix_retrieval_chunk_embeddings_chunk_id",
        "retrieval_chunk_embeddings",
        ["chunk_id"],
    )
    op.create_index(
        "ix_retrieval_chunk_embeddings_document_id",
        "retrieval_chunk_embeddings",
        ["document_id"],
    )
    op.create_index(
        "ix_retrieval_chunk_embeddings_source_id",
        "retrieval_chunk_embeddings",
        ["source_id"],
    )

    op.execute(
        """
        INSERT INTO retrieval_chunk_embeddings (
            embedding_id,
            chunk_id,
            document_id,
            source_id,
            embedding_model,
            embedding_status,
            vector_dimensions,
            content_checksum
        )
        VALUES
            (
                'emb_chunk_rfc_0068_0001',
                'chunk_rfc_0068_0001',
                'lotus-platform-rfc-0068',
                'lotus-platform-rfcs',
                'foundation.text-embedding-preview',
                'STAGED',
                1536,
                'sha256:chunk-rfc-0068-0001'
            ),
            (
                'emb_chunk_rfc_0069_0001',
                'chunk_rfc_0069_0001',
                'lotus-platform-rfc-0069',
                'lotus-platform-rfcs',
                'foundation.text-embedding-preview',
                'STAGED',
                1536,
                'sha256:chunk-rfc-0069-0001'
            ),
            (
                'emb_chunk_system_overview_0001',
                'chunk_system_overview_0001',
                'lotus-ai-system-overview',
                'lotus-ai-architecture',
                'foundation.text-embedding-preview',
                'STAGED',
                1536,
                'sha256:chunk-system-overview-0001'
            ),
            (
                'emb_chunk_retrieval_guide_0001',
                'chunk_retrieval_guide_0001',
                'lotus-ai-retrieval-vector-store-guide',
                'lotus-ai-architecture',
                'foundation.text-embedding-preview',
                'STAGED',
                1536,
                'sha256:chunk-retrieval-guide-0001'
            )
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_retrieval_chunk_embeddings_source_id", table_name="retrieval_chunk_embeddings"
    )
    op.drop_index(
        "ix_retrieval_chunk_embeddings_document_id", table_name="retrieval_chunk_embeddings"
    )
    op.drop_index("ix_retrieval_chunk_embeddings_chunk_id", table_name="retrieval_chunk_embeddings")
    op.drop_table("retrieval_chunk_embeddings")
    op.drop_column("retrieval_chunks", "content_checksum")
