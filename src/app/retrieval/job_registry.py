from __future__ import annotations

from fastapi import HTTPException, status

from app.config import settings
from app.repositories.async_runtime_repository import AsyncRuntimeJobRecord
from app.contracts.retrieval import (
    RetrievalIndexJobCatalogResponse,
    RetrievalIndexJobDescriptor,
    RetrievalIndexJobDetailResponse,
    RetrievalIndexJobStepDescriptor,
    RetrievalIndexingPolicyResponse,
    RetrievalJobStatus,
    RetrievalPipelineStage,
    RetrievalRuntimeStatusResponse,
)
from app.retrieval.inventory_summary import (
    RetrievalRuntimeInventorySummary,
    summarize_retrieval_runtime_inventory,
    summarize_retrieval_source_inventory,
)
from app.retrieval.policy import (
    CHUNKING_STRATEGY,
    PERSISTENCE_STRATEGY,
    VECTOR_STORE_STRATEGY,
)
from app.services.retrieval_store import get_retrieval_repository
from app.services.retrieval_embedding_runtime import build_retrieval_embedding_runtime
from app.services.runtime_readiness import get_retrieval_store_runtime_status
from app.services.async_runtime_store import get_async_runtime_store


def _build_job_descriptor(source_id: str) -> RetrievalIndexJobDescriptor:
    repository = get_retrieval_repository()
    job_id = f"retjob_{source_id.replace('-', '_')}"
    descriptor = repository.get_index_job(job_id)
    runtime_job = _get_runtime_async_retrieval_job(job_id=job_id)
    if descriptor is not None:
        return _overlay_runtime_status(descriptor=descriptor, runtime_job=runtime_job)

    inventory = summarize_retrieval_source_inventory(source_id)
    descriptor = RetrievalIndexJobDescriptor(
        job_id=job_id,
        source_id=source_id,
        status=(
            RetrievalJobStatus.PENDING
            if inventory.document_count == 0
            else RetrievalJobStatus.STAGED
        ),
        document_count=inventory.document_count,
        chunk_count=inventory.chunk_count,
        message=(
            "No staged documents yet for this retrieval source."
            if inventory.document_count == 0
            else "Documents are staged for indexing, but vector indexing is not enabled yet."
        ),
    )
    return _overlay_runtime_status(descriptor=descriptor, runtime_job=runtime_job)


def build_retrieval_job_catalog() -> RetrievalIndexJobCatalogResponse:
    jobs = [
        _build_job_descriptor(source_id)
        for source_id in get_retrieval_repository().list_source_ids()
    ]
    return RetrievalIndexJobCatalogResponse(
        service=settings.service_name,
        vector_store=VECTOR_STORE_STRATEGY,
        jobs=jobs,
    )


def get_retrieval_job_detail(job_id: str) -> RetrievalIndexJobDetailResponse:
    for source_id in get_retrieval_repository().list_source_ids():
        descriptor = _build_job_descriptor(source_id)
        if descriptor.job_id == job_id:
            runtime_job = _get_runtime_async_retrieval_job(job_id=job_id)
            return RetrievalIndexJobDetailResponse(
                service=settings.service_name,
                vector_store=VECTOR_STORE_STRATEGY,
                embedding_provider_mode=settings.embedding_provider_mode,
                job=descriptor,
                steps=[
                    RetrievalIndexJobStepDescriptor(
                        step_id=f"{job_id}.source_curation",
                        name="Source curation",
                        stage=RetrievalPipelineStage.STAGED,
                        runtime_status=None,
                        linked_async_job_id=None,
                        description=(
                            "Approved source inventory is explicitly curated before indexing is enabled."
                        ),
                    ),
                    RetrievalIndexJobStepDescriptor(
                        step_id=f"{job_id}.document_inventory",
                        name="Document inventory",
                        stage=(
                            RetrievalPipelineStage.ENABLED
                            if descriptor.status == RetrievalJobStatus.COMPLETED
                            else RetrievalPipelineStage.STAGED
                        ),
                        runtime_status=None,
                        linked_async_job_id=None,
                        description=(
                            "Documents and staged chunk counts are visible through the retrieval catalog."
                        ),
                    ),
                    RetrievalIndexJobStepDescriptor(
                        step_id=f"{job_id}.async_execution",
                        name="Async retrieval execution",
                        stage=(
                            RetrievalPipelineStage.ENABLED
                            if runtime_job is not None
                            else RetrievalPipelineStage.STAGED
                        ),
                        runtime_status=None
                        if runtime_job is None
                        else runtime_job.lifecycle_status,
                        linked_async_job_id=None if runtime_job is None else runtime_job.job_id,
                        description=(
                            "Runtime-backed retrieval indexing now executes through the durable async runtime for allowlisted jobs."
                        ),
                    ),
                    RetrievalIndexJobStepDescriptor(
                        step_id=f"{job_id}.embedding_generation",
                        name="Embedding generation",
                        stage=(
                            RetrievalPipelineStage.ENABLED
                            if descriptor.status == RetrievalJobStatus.COMPLETED
                            else RetrievalPipelineStage.STAGED
                        ),
                        runtime_status=None
                        if runtime_job is None
                        else runtime_job.lifecycle_status,
                        linked_async_job_id=None if runtime_job is None else runtime_job.job_id,
                        description=(
                            "Embedding generation is bounded and governed through the selected embedding provider path for the current retrieval indexing runtime posture."
                        ),
                    ),
                    RetrievalIndexJobStepDescriptor(
                        step_id=f"{job_id}.vector_persistence",
                        name="Vector persistence",
                        stage=(
                            RetrievalPipelineStage.ENABLED
                            if descriptor.status == RetrievalJobStatus.COMPLETED
                            else RetrievalPipelineStage.STAGED
                        ),
                        runtime_status=None
                        if runtime_job is None
                        else runtime_job.lifecycle_status,
                        linked_async_job_id=None if runtime_job is None else runtime_job.job_id,
                        description=(
                            "Durable vector persistence remains PostgreSQL with pgvector and now reflects runtime-backed retrieval indexing completion."
                        ),
                    ),
                ],
            )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Unknown retrieval job_id: {job_id}",
    )


def build_retrieval_indexing_policy() -> RetrievalIndexingPolicyResponse:
    embedding_runtime = build_retrieval_embedding_runtime()
    return RetrievalIndexingPolicyResponse(
        service=settings.service_name,
        vector_store=VECTOR_STORE_STRATEGY,
        retrieval_mode=settings.retrieval_mode,
        retrieval_store_mode=settings.retrieval_store_mode,
        embedding_provider_mode=settings.embedding_provider_mode,
        embedding_execution_enabled=embedding_runtime.embedding_execution_enabled,
        embedding_provider_id=embedding_runtime.embedding_provider_id,
        embedding_model_id=embedding_runtime.embedding_model_id,
        chunking_strategy=CHUNKING_STRATEGY,
        embedding_strategy=embedding_runtime.embedding_strategy,
        persistence_strategy=PERSISTENCE_STRATEGY,
        execution_stage=RetrievalPipelineStage.ENABLED,
        notes=[
            "Retrieval indexing can now run through the durable async runtime for allowlisted job targets.",
            "Approved source curation is required before any document enters the retrieval corpus.",
            "PostgreSQL with pgvector remains the first vector-store architecture for lotus-ai.",
            *embedding_runtime.findings,
        ],
    )


def build_retrieval_runtime_status() -> RetrievalRuntimeStatusResponse:
    store_status = get_retrieval_store_runtime_status()
    if store_status.status == "READY":
        inventory = summarize_retrieval_runtime_inventory()
        repository = get_retrieval_repository()
        document_version_count = len(repository.list_document_versions())
        ingestion_job_count = len(repository.list_ingestion_jobs())
    else:
        inventory = RetrievalRuntimeInventorySummary(
            source_count=0,
            document_count=0,
            chunk_count=0,
            index_job_count=0,
        )
        document_version_count = 0
        ingestion_job_count = 0
    return RetrievalRuntimeStatusResponse(
        service=settings.service_name,
        delivery_phase=settings.delivery_phase,
        retrieval_mode=settings.retrieval_mode,
        retrieval_store_mode=settings.retrieval_store_mode,
        retrieval_store_status=store_status.status,
        retrieval_store_detail=store_status.detail,
        database_configured=store_status.database_configured,
        vector_store=VECTOR_STORE_STRATEGY,
        source_count=inventory.source_count,
        document_count=inventory.document_count,
        chunk_count=inventory.chunk_count,
        index_job_count=inventory.index_job_count,
        document_version_count=document_version_count,
        ingestion_job_count=ingestion_job_count,
    )


def _get_runtime_async_retrieval_job(job_id: str) -> AsyncRuntimeJobRecord | None:
    jobs = [
        job
        for job in get_async_runtime_store().list_jobs()
        if job.job_type == "retrieval_indexing" and job.target_id == job_id
    ]
    if not jobs:
        return None
    return max(jobs, key=lambda item: item.submitted_at)


def _overlay_runtime_status(
    *,
    descriptor: RetrievalIndexJobDescriptor,
    runtime_job: AsyncRuntimeJobRecord | None,
) -> RetrievalIndexJobDescriptor:
    if runtime_job is None:
        return descriptor
    return RetrievalIndexJobDescriptor(
        job_id=descriptor.job_id,
        source_id=descriptor.source_id,
        status=RetrievalJobStatus(runtime_job.lifecycle_status),
        document_count=descriptor.document_count,
        chunk_count=descriptor.chunk_count,
        message=runtime_job.latest_message,
    )
