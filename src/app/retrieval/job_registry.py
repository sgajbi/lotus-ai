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
from app.retrieval.document_registry import document_chunk_count
from app.retrieval.policy import (
    CHUNKING_STRATEGY,
    EMBEDDING_STRATEGY,
    PERSISTENCE_STRATEGY,
    VECTOR_STORE_STRATEGY,
)
from app.services.retrieval_store import get_retrieval_repository


def _build_job_descriptor(source_id: str) -> RetrievalIndexJobDescriptor:
    repository = get_retrieval_repository()
    job_id = f"retjob_{source_id.replace('-', '_')}"
    descriptor = repository.get_index_job(job_id)
    if descriptor is not None:
        return descriptor

    documents = repository.list_documents_for_source(source_id)
    chunk_count = sum(document_chunk_count(document.document_id) for document in documents)
    return RetrievalIndexJobDescriptor(
        job_id=job_id,
        source_id=source_id,
        status=RetrievalJobStatus.PENDING if not documents else RetrievalJobStatus.STAGED,
        document_count=len(documents),
        chunk_count=chunk_count,
        message=(
            "No staged documents yet for this retrieval source."
            if not documents
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
    repository = get_retrieval_repository()
    sources = repository.list_sources()
    documents = [
        document
        for source in sources
        for document in repository.list_documents_for_source(source.source_id)
    ]
    chunks = [
        chunk
        for document in documents
        for chunk in repository.list_chunks_for_document(document.document_id)
    ]
    jobs = repository.list_index_jobs()
    return RetrievalRuntimeStatusResponse(
        service=settings.service_name,
        delivery_phase=settings.delivery_phase,
        retrieval_mode=settings.retrieval_mode,
        retrieval_store_mode=settings.retrieval_store_mode,
        database_configured=bool(settings.database_url),
        vector_store=VECTOR_STORE_STRATEGY,
        source_count=len(sources),
        document_count=len(documents),
        chunk_count=len(chunks),
        index_job_count=len(jobs),
    )
