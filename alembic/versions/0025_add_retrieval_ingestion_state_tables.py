"""Add retrieval ingestion state tables.

Revision ID: 0025_add_retrieval_ingestion_state_tables
Revises: 0024_seed_lotus_performance_caller_policy
Create Date: 2026-03-24 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0025_add_retrieval_ingestion_state_tables"
down_revision = "0024_seed_lotus_performance_caller_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "retrieval_document_versions",
        sa.Column("version_id", sa.String(length=128), primary_key=True, nullable=False),
        sa.Column("document_id", sa.String(length=128), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=32), nullable=False),
        sa.Column("refresh_action", sa.String(length=32), nullable=False),
        sa.Column("lineage_parent_version_id", sa.String(length=128), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["retrieval_documents.document_id"]),
        sa.ForeignKeyConstraint(["source_id"], ["retrieval_sources.source_id"]),
    )
    op.create_index(
        "ix_retrieval_document_versions_document_id",
        "retrieval_document_versions",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_retrieval_document_versions_source_id",
        "retrieval_document_versions",
        ["source_id"],
        unique=False,
    )
    op.create_index(
        "ix_retrieval_document_versions_lifecycle_status",
        "retrieval_document_versions",
        ["lifecycle_status"],
        unique=False,
    )
    op.create_index(
        "ix_retrieval_document_versions_created_at",
        "retrieval_document_versions",
        ["created_at"],
        unique=False,
    )

    op.create_table(
        "retrieval_ingestion_jobs",
        sa.Column("job_id", sa.String(length=128), primary_key=True, nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("document_id", sa.String(length=128), nullable=True),
        sa.Column("target_version_id", sa.String(length=128), nullable=True),
        sa.Column("requested_action", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("requested_at", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["retrieval_documents.document_id"]),
        sa.ForeignKeyConstraint(["source_id"], ["retrieval_sources.source_id"]),
    )
    op.create_index(
        "ix_retrieval_ingestion_jobs_source_id",
        "retrieval_ingestion_jobs",
        ["source_id"],
        unique=False,
    )
    op.create_index(
        "ix_retrieval_ingestion_jobs_document_id",
        "retrieval_ingestion_jobs",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_retrieval_ingestion_jobs_target_version_id",
        "retrieval_ingestion_jobs",
        ["target_version_id"],
        unique=False,
    )
    op.create_index(
        "ix_retrieval_ingestion_jobs_status",
        "retrieval_ingestion_jobs",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_retrieval_ingestion_jobs_requested_at",
        "retrieval_ingestion_jobs",
        ["requested_at"],
        unique=False,
    )

    document_version_table = sa.table(
        "retrieval_document_versions",
        sa.column("version_id", sa.String()),
        sa.column("document_id", sa.String()),
        sa.column("source_id", sa.String()),
        sa.column("lifecycle_status", sa.String()),
        sa.column("refresh_action", sa.String()),
        sa.column("lineage_parent_version_id", sa.String()),
        sa.column("title", sa.Text()),
        sa.column("location", sa.Text()),
        sa.column("created_at", sa.String()),
        sa.column("created_by", sa.String()),
        sa.column("notes", sa.Text()),
    )
    ingestion_job_table = sa.table(
        "retrieval_ingestion_jobs",
        sa.column("job_id", sa.String()),
        sa.column("source_id", sa.String()),
        sa.column("document_id", sa.String()),
        sa.column("target_version_id", sa.String()),
        sa.column("requested_action", sa.String()),
        sa.column("status", sa.String()),
        sa.column("requested_by", sa.String()),
        sa.column("requested_at", sa.String()),
        sa.column("message", sa.Text()),
    )

    op.bulk_insert(
        document_version_table,
        [
            {
                "version_id": "ver_lotus_platform_rfc_0068_2026_03_22",
                "document_id": "lotus-platform-rfc-0068",
                "source_id": "lotus-platform-rfcs",
                "lifecycle_status": "ACTIVE",
                "refresh_action": "ONBOARD",
                "lineage_parent_version_id": None,
                "title": "RFC-0068 Centralized Shared Infrastructure Ownership and Migration",
                "location": "lotus-platform/rfcs/RFC-0068-centralized-shared-infrastructure-ownership-and-migration.md",
                "created_at": "2026-03-22T09:00:00Z",
                "created_by": "migration-seed",
                "notes": "Seeded active retrieval document version for the approved RFC corpus.",
            },
            {
                "version_id": "ver_lotus_platform_rfc_0069_2026_03_15",
                "document_id": "lotus-platform-rfc-0069",
                "source_id": "lotus-platform-rfcs",
                "lifecycle_status": "SUPERSEDED",
                "refresh_action": "ONBOARD",
                "lineage_parent_version_id": None,
                "title": "RFC-0069 lotus-ai Shared AI Platform Service",
                "location": "lotus-platform/rfcs/RFC-0069-lotus-ai-shared-ai-platform-service.md",
                "created_at": "2026-03-15T09:00:00Z",
                "created_by": "migration-seed",
                "notes": "Historical seed version retained to prove supersession lineage.",
            },
            {
                "version_id": "ver_lotus_platform_rfc_0069_2026_03_22",
                "document_id": "lotus-platform-rfc-0069",
                "source_id": "lotus-platform-rfcs",
                "lifecycle_status": "ACTIVE",
                "refresh_action": "REFRESH",
                "lineage_parent_version_id": "ver_lotus_platform_rfc_0069_2026_03_15",
                "title": "RFC-0069 lotus-ai Shared AI Platform Service",
                "location": "lotus-platform/rfcs/RFC-0069-lotus-ai-shared-ai-platform-service.md",
                "created_at": "2026-03-22T10:00:00Z",
                "created_by": "migration-seed",
                "notes": "Current approved version after a bounded corpus refresh.",
            },
            {
                "version_id": "ver_lotus_platform_observability_standards_2026_03_21",
                "document_id": "lotus-platform-observability-standards",
                "source_id": "lotus-platform-standards",
                "lifecycle_status": "WITHDRAWN",
                "refresh_action": "WITHDRAW",
                "lineage_parent_version_id": None,
                "title": "Platform Observability Standards",
                "location": "lotus-platform/Platform Observability Standards.md",
                "created_at": "2026-03-21T08:30:00Z",
                "created_by": "migration-seed",
                "notes": "Withdrawn seed version kept visible for governance review.",
            },
            {
                "version_id": "ver_lotus_ai_system_overview_2026_03_22",
                "document_id": "lotus-ai-system-overview",
                "source_id": "lotus-ai-architecture",
                "lifecycle_status": "ACTIVE",
                "refresh_action": "ONBOARD",
                "lineage_parent_version_id": None,
                "title": "lotus-ai System Overview",
                "location": "lotus-ai/docs/architecture/system-overview.md",
                "created_at": "2026-03-22T09:15:00Z",
                "created_by": "migration-seed",
                "notes": "Seeded active architecture document version.",
            },
            {
                "version_id": "ver_lotus_ai_retrieval_vector_store_2026_03_22",
                "document_id": "lotus-ai-retrieval-vector-store-guide",
                "source_id": "lotus-ai-architecture",
                "lifecycle_status": "ACTIVE",
                "refresh_action": "ONBOARD",
                "lineage_parent_version_id": None,
                "title": "lotus-ai Retrieval and Vector Store Guide",
                "location": "lotus-ai/docs/guides/retrieval-and-vector-store.md",
                "created_at": "2026-03-22T09:30:00Z",
                "created_by": "migration-seed",
                "notes": "Seeded active retrieval strategy document version.",
            },
        ],
    )

    op.bulk_insert(
        ingestion_job_table,
        [
            {
                "job_id": "ingjob_lotus_platform_rfcs_refresh_0069",
                "source_id": "lotus-platform-rfcs",
                "document_id": "lotus-platform-rfc-0069",
                "target_version_id": "ver_lotus_platform_rfc_0069_2026_03_22",
                "requested_action": "REFRESH",
                "status": "STAGED",
                "requested_by": "migration-seed",
                "requested_at": "2026-03-22T10:00:00Z",
                "message": "Refresh request is recorded durably, but live ingestion execution is not enabled yet.",
            },
            {
                "job_id": "ingjob_lotus_platform_standards_withdraw_obs",
                "source_id": "lotus-platform-standards",
                "document_id": "lotus-platform-observability-standards",
                "target_version_id": "ver_lotus_platform_observability_standards_2026_03_21",
                "requested_action": "WITHDRAW",
                "status": "RECORDED",
                "requested_by": "migration-seed",
                "requested_at": "2026-03-21T08:30:00Z",
                "message": "Withdrawal posture is durably recorded for governance review.",
            },
            {
                "job_id": "ingjob_lotus_openapi_onboard_pending",
                "source_id": "lotus-openapi-derived",
                "document_id": None,
                "target_version_id": None,
                "requested_action": "ONBOARD",
                "status": "BLOCKED",
                "requested_by": "migration-seed",
                "requested_at": "2026-03-23T07:45:00Z",
                "message": "OpenAPI-derived corpus onboarding remains blocked until approved runtime ingestion exists.",
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_retrieval_ingestion_jobs_requested_at", table_name="retrieval_ingestion_jobs")
    op.drop_index("ix_retrieval_ingestion_jobs_status", table_name="retrieval_ingestion_jobs")
    op.drop_index(
        "ix_retrieval_ingestion_jobs_target_version_id",
        table_name="retrieval_ingestion_jobs",
    )
    op.drop_index("ix_retrieval_ingestion_jobs_document_id", table_name="retrieval_ingestion_jobs")
    op.drop_index("ix_retrieval_ingestion_jobs_source_id", table_name="retrieval_ingestion_jobs")
    op.drop_table("retrieval_ingestion_jobs")

    op.drop_index(
        "ix_retrieval_document_versions_created_at",
        table_name="retrieval_document_versions",
    )
    op.drop_index(
        "ix_retrieval_document_versions_lifecycle_status",
        table_name="retrieval_document_versions",
    )
    op.drop_index(
        "ix_retrieval_document_versions_source_id",
        table_name="retrieval_document_versions",
    )
    op.drop_index(
        "ix_retrieval_document_versions_document_id",
        table_name="retrieval_document_versions",
    )
    op.drop_table("retrieval_document_versions")
