from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_create_retrieval_metadata_tables"
down_revision = "0001_create_audit_records_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "retrieval_sources",
        sa.Column("source_id", sa.String(length=128), primary_key=True, nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
    )
    op.create_table(
        "retrieval_documents",
        sa.Column("document_id", sa.String(length=128), primary_key=True, nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("index_status", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["retrieval_sources.source_id"]),
    )
    op.create_index(
        "ix_retrieval_documents_source_id",
        "retrieval_documents",
        ["source_id"],
        unique=False,
    )
    op.create_table(
        "retrieval_chunks",
        sa.Column("chunk_id", sa.String(length=128), primary_key=True, nullable=False),
        sa.Column("document_id", sa.String(length=128), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("chunk_order", sa.Integer(), nullable=False),
        sa.Column("token_estimate", sa.Integer(), nullable=False),
        sa.Column("preview", sa.Text(), nullable=False),
        sa.Column("index_status", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["retrieval_documents.document_id"]),
        sa.ForeignKeyConstraint(["source_id"], ["retrieval_sources.source_id"]),
    )
    op.create_index(
        "ix_retrieval_chunks_document_id",
        "retrieval_chunks",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_retrieval_chunks_source_id",
        "retrieval_chunks",
        ["source_id"],
        unique=False,
    )
    op.create_table(
        "retrieval_index_jobs",
        sa.Column("job_id", sa.String(length=128), primary_key=True, nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["retrieval_sources.source_id"]),
    )
    op.create_index(
        "ix_retrieval_index_jobs_source_id",
        "retrieval_index_jobs",
        ["source_id"],
        unique=False,
    )

    source_table = sa.table(
        "retrieval_sources",
        sa.column("source_id", sa.String()),
        sa.column("kind", sa.String()),
        sa.column("enabled", sa.Boolean()),
        sa.column("description", sa.Text()),
    )
    document_table = sa.table(
        "retrieval_documents",
        sa.column("document_id", sa.String()),
        sa.column("source_id", sa.String()),
        sa.column("title", sa.Text()),
        sa.column("location", sa.Text()),
        sa.column("index_status", sa.String()),
    )
    chunk_table = sa.table(
        "retrieval_chunks",
        sa.column("chunk_id", sa.String()),
        sa.column("document_id", sa.String()),
        sa.column("source_id", sa.String()),
        sa.column("chunk_order", sa.Integer()),
        sa.column("token_estimate", sa.Integer()),
        sa.column("preview", sa.Text()),
        sa.column("index_status", sa.String()),
    )
    job_table = sa.table(
        "retrieval_index_jobs",
        sa.column("job_id", sa.String()),
        sa.column("source_id", sa.String()),
        sa.column("status", sa.String()),
        sa.column("message", sa.Text()),
    )

    op.bulk_insert(
        source_table,
        [
            {
                "source_id": "lotus-platform-rfcs",
                "kind": "RFC",
                "enabled": False,
                "description": "Approved Lotus platform RFC documents.",
            },
            {
                "source_id": "lotus-platform-standards",
                "kind": "STANDARD",
                "enabled": False,
                "description": "Approved Lotus standards and governance documents.",
            },
            {
                "source_id": "lotus-ai-architecture",
                "kind": "ARCHITECTURE",
                "enabled": False,
                "description": "lotus-ai architecture, guides, and service-local design documentation.",
            },
            {
                "source_id": "lotus-openapi-derived",
                "kind": "OPENAPI",
                "enabled": False,
                "description": "OpenAPI-derived documentation and approved schema references.",
            },
        ],
    )
    op.bulk_insert(
        document_table,
        [
            {
                "document_id": "lotus-platform-rfc-0068",
                "source_id": "lotus-platform-rfcs",
                "title": "RFC-0068 Centralized Shared Infrastructure Ownership and Migration",
                "location": "lotus-platform/rfcs/RFC-0068-centralized-shared-infrastructure-ownership-and-migration.md",
                "index_status": "STAGED",
            },
            {
                "document_id": "lotus-platform-rfc-0069",
                "source_id": "lotus-platform-rfcs",
                "title": "RFC-0069 lotus-ai Shared AI Platform Service",
                "location": "lotus-platform/rfcs/RFC-0069-lotus-ai-shared-ai-platform-service.md",
                "index_status": "STAGED",
            },
            {
                "document_id": "lotus-platform-observability-standards",
                "source_id": "lotus-platform-standards",
                "title": "Platform Observability Standards",
                "location": "lotus-platform/Platform Observability Standards.md",
                "index_status": "STAGED",
            },
            {
                "document_id": "lotus-ai-system-overview",
                "source_id": "lotus-ai-architecture",
                "title": "lotus-ai System Overview",
                "location": "lotus-ai/docs/architecture/system-overview.md",
                "index_status": "STAGED",
            },
            {
                "document_id": "lotus-ai-retrieval-vector-store-guide",
                "source_id": "lotus-ai-architecture",
                "title": "lotus-ai Retrieval and Vector Store Guide",
                "location": "lotus-ai/docs/guides/retrieval-and-vector-store.md",
                "index_status": "STAGED",
            },
        ],
    )
    op.bulk_insert(
        chunk_table,
        [
            {
                "chunk_id": "chunk_rfc_0068_0001",
                "document_id": "lotus-platform-rfc-0068",
                "source_id": "lotus-platform-rfcs",
                "chunk_order": 1,
                "token_estimate": 180,
                "preview": "Move ownership of shared platform infrastructure to lotus-platform.",
                "index_status": "STAGED",
            },
            {
                "chunk_id": "chunk_rfc_0069_0001",
                "document_id": "lotus-platform-rfc-0069",
                "source_id": "lotus-platform-rfcs",
                "chunk_order": 1,
                "token_estimate": 210,
                "preview": "Introduce lotus-ai as a dedicated shared AI platform service for Lotus applications.",
                "index_status": "STAGED",
            },
            {
                "chunk_id": "chunk_obs_0001",
                "document_id": "lotus-platform-observability-standards",
                "source_id": "lotus-platform-standards",
                "chunk_order": 1,
                "token_estimate": 165,
                "preview": "Cross-cutting governance for this stack is defined in Platform Observability Standards.",
                "index_status": "STAGED",
            },
            {
                "chunk_id": "chunk_system_overview_0001",
                "document_id": "lotus-ai-system-overview",
                "source_id": "lotus-ai-architecture",
                "chunk_order": 1,
                "token_estimate": 170,
                "preview": "lotus-ai is the shared AI platform service for Lotus.",
                "index_status": "STAGED",
            },
            {
                "chunk_id": "chunk_retrieval_guide_0001",
                "document_id": "lotus-ai-retrieval-vector-store-guide",
                "source_id": "lotus-ai-architecture",
                "chunk_order": 1,
                "token_estimate": 190,
                "preview": "The first vector-store architecture for lotus-ai is PostgreSQL plus pgvector.",
                "index_status": "STAGED",
            },
        ],
    )
    op.bulk_insert(
        job_table,
        [
            {
                "job_id": "retjob_lotus_platform_rfcs",
                "source_id": "lotus-platform-rfcs",
                "status": "STAGED",
                "message": "Documents are staged for indexing, but vector indexing is not enabled yet.",
            },
            {
                "job_id": "retjob_lotus_platform_standards",
                "source_id": "lotus-platform-standards",
                "status": "STAGED",
                "message": "Documents are staged for indexing, but vector indexing is not enabled yet.",
            },
            {
                "job_id": "retjob_lotus_ai_architecture",
                "source_id": "lotus-ai-architecture",
                "status": "STAGED",
                "message": "Documents are staged for indexing, but vector indexing is not enabled yet.",
            },
            {
                "job_id": "retjob_lotus_openapi_derived",
                "source_id": "lotus-openapi-derived",
                "status": "PENDING",
                "message": "No staged documents yet for this retrieval source.",
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_retrieval_index_jobs_source_id", table_name="retrieval_index_jobs")
    op.drop_table("retrieval_index_jobs")
    op.drop_index("ix_retrieval_chunks_source_id", table_name="retrieval_chunks")
    op.drop_index("ix_retrieval_chunks_document_id", table_name="retrieval_chunks")
    op.drop_table("retrieval_chunks")
    op.drop_index("ix_retrieval_documents_source_id", table_name="retrieval_documents")
    op.drop_table("retrieval_documents")
    op.drop_table("retrieval_sources")
