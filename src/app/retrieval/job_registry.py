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
)
from app.retrieval.document_registry import DOCUMENTS, document_chunk_count
from app.retrieval.source_registry import VECTOR_STORE_STRATEGY

CHUNKING_STRATEGY = "markdown-section-v1"
EMBEDDING_STRATEGY = "provider-disabled"
PERSISTENCE_STRATEGY = "postgresql+pgvector"


def _build_job_descriptor(source_id: str) -> RetrievalIndexJobDescriptor:
    documents = DOCUMENTS.get(source_id, [])
    chunk_count = sum(document_chunk_count(document.document_id) for document in documents)
    if not documents:
        status_value = RetrievalJobStatus.PENDING
        message = "No staged documents yet for this retrieval source."
    else:
        status_value = RetrievalJobStatus.STAGED
        message = "Documents are staged for indexing, but vector indexing is not enabled yet."

    return RetrievalIndexJobDescriptor(
        job_id=f"retjob_{source_id.replace('-', '_')}",
        source_id=source_id,
        status=status_value,
        document_count=len(documents),
        chunk_count=chunk_count,
        message=message,
    )


def build_retrieval_job_catalog() -> RetrievalIndexJobCatalogResponse:
    jobs = [_build_job_descriptor(source_id) for source_id in DOCUMENTS]
    return RetrievalIndexJobCatalogResponse(
        service=settings.service_name,
        vector_store=VECTOR_STORE_STRATEGY,
        jobs=jobs,
    )


def get_retrieval_job_detail(job_id: str) -> RetrievalIndexJobDetailResponse:
    for source_id in DOCUMENTS:
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
