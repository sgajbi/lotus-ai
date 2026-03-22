from __future__ import annotations

from fastapi import HTTPException, status

from app.config import settings
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
    EMBEDDING_STRATEGY,
    PERSISTENCE_STRATEGY,
    VECTOR_STORE_STRATEGY,
)
from app.services.retrieval_store import get_retrieval_repository
from app.services.runtime_readiness import get_retrieval_store_runtime_status


def _build_job_descriptor(source_id: str) -> RetrievalIndexJobDescriptor:
    repository = get_retrieval_repository()
    job_id = f"retjob_{source_id.replace('-', '_')}"
    descriptor = repository.get_index_job(job_id)
    if descriptor is not None:
        return descriptor

    inventory = summarize_retrieval_source_inventory(source_id)
    return RetrievalIndexJobDescriptor(
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
                        description=(
                            "Approved source inventory is explicitly curated before indexing is enabled."
                        ),
                    ),
                    RetrievalIndexJobStepDescriptor(
                        step_id=f"{job_id}.document_inventory",
                        name="Document inventory",
                        stage=RetrievalPipelineStage.STAGED,
                        description=(
                            "Documents and staged chunk counts are visible through the retrieval catalog."
                        ),
                    ),
                    RetrievalIndexJobStepDescriptor(
                        step_id=f"{job_id}.embedding_generation",
                        name="Embedding generation",
                        stage=RetrievalPipelineStage.DOCUMENTED,
                        description=(
                            "Embedding generation is designed but not yet enabled in runtime execution."
                        ),
                    ),
                    RetrievalIndexJobStepDescriptor(
                        step_id=f"{job_id}.vector_persistence",
                        name="Vector persistence",
                        stage=RetrievalPipelineStage.DOCUMENTED,
                        description=(
                            "Durable vector persistence will use PostgreSQL with pgvector when enabled."
                        ),
                    ),
                ],
            )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Unknown retrieval job_id: {job_id}",
    )


def build_retrieval_indexing_policy() -> RetrievalIndexingPolicyResponse:
    return RetrievalIndexingPolicyResponse(
        service=settings.service_name,
        vector_store=VECTOR_STORE_STRATEGY,
        retrieval_mode=settings.retrieval_mode,
        retrieval_store_mode=settings.retrieval_store_mode,
        embedding_provider_mode=settings.embedding_provider_mode,
        chunking_strategy=CHUNKING_STRATEGY,
        embedding_strategy=EMBEDDING_STRATEGY,
        persistence_strategy=PERSISTENCE_STRATEGY,
        execution_stage=RetrievalPipelineStage.DOCUMENTED,
        notes=[
            "Indexing remains staged until retrieval execution and embedding generation are enabled.",
            "Approved source curation is required before any document enters the retrieval corpus.",
            "PostgreSQL with pgvector remains the first vector-store architecture for lotus-ai.",
        ],
    )


def build_retrieval_runtime_status() -> RetrievalRuntimeStatusResponse:
    store_status = get_retrieval_store_runtime_status()
    if store_status.status == "READY":
        inventory = summarize_retrieval_runtime_inventory()
    else:
        inventory = RetrievalRuntimeInventorySummary(
            source_count=0,
            document_count=0,
            chunk_count=0,
            index_job_count=0,
        )
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
    )
